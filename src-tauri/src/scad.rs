//! 调用 Python jig_generator.py 生成 STL/STEP
//!
//! 工作流:
//! 1. 把 ScadParams 写到临时 JSON 文件
//! 2. 调用 python jig_generator.py --input json --output stl --part base
//! 3. 读取生成的 STL 字节返回
//!
//! Python 路径优先级:
//! 1. 用户配置(set_python_path 调用 set 进去)
//! 2. 系统搜索: `python3` / `python` / `py`
//!
//! Python 依赖(必须先装好):
//!   pip install build123d shapely numpy
use crate::commands::{Part, ScadParams};
use crate::error::AppError;
use crate::openscad_detect;
use serde::Serialize;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Stdio;
use tokio::io::AsyncReadExt;
use tokio::process::Command;
use tokio::time::{timeout, Duration};

/// 把 ScadParams 序列化成 JSON
#[derive(Serialize)]
struct PythonInput<'a> {
    pcb_size_x: f64,
    pcb_size_y: f64,
    pcb_thickness: f64,
    pcb_pocket_clearance: f64,
    pcb_outline_points: &'a [[f64; 2]],
    stencil_size: f64,
    screw_spacing: f64,
    base_height: f64,
    top_cover_height: f64,
    post_diameter: f64,
    post_height: f64,
    thumbscrew_head_d: f64,
    thumbscrew_clearance_d: f64,
    jig_size: f64,
    insert_height: f64,
    pcb_support_radius: f64,
    pcb_support_offset: f64,
}

impl Part {
    fn to_str(&self) -> &'static str {
        match self {
            Part::Base => "base",
            Part::PcbInsert => "insert",
            Part::TopCover => "cover",
        }
    }
}

/// 解析 Python 可执行文件路径:已配置 > 系统搜索 > 常见路径
fn resolve_python(configured: Option<&str>) -> Option<String> {
    if let Some(p) = configured {
        if !p.is_empty() && Path::new(p).exists() {
            return Some(p.to_string());
        }
    }
    openscad_detect::detect_python()
}

/// 工作目录:系统临时目录下,每次生成一个独立子目录
fn work_dir() -> Result<PathBuf, AppError> {
    let base = std::env::temp_dir().join("pcb-jig-work");
    fs::create_dir_all(&base).map_err(|e| AppError::Io(format!("创建工作目录失败: {}", e)))?;
    let sub = base.join(format!("jig-{}", uuid::Uuid::new_v4()));
    fs::create_dir_all(&sub).map_err(|e| AppError::Io(format!("创建工作子目录失败: {}", e)))?;
    Ok(sub)
}

/// 调用 Python 脚本生成 STL/STEP,返回字节
async fn run_python(
    python_path: &str,
    params: &ScadParams,
    part: Part,
    work: &Path,
    output_path: &Path,
    script_path: &Path,
) -> Result<(), AppError> {
    // 写 JSON 输入
    let input_path = work.join("input.json");
    let input = PythonInput {
        pcb_size_x: params.pcb_size_x,
        pcb_size_y: params.pcb_size_y,
        pcb_thickness: params.pcb_thickness,
        pcb_pocket_clearance: params.pcb_pocket_clearance,
        pcb_outline_points: &params.pcb_outline_points,
        stencil_size: params.stencil_size,
        screw_spacing: params.screw_spacing,
        base_height: params.base_height,
        top_cover_height: params.top_cover_height,
        post_diameter: params.post_diameter,
        post_height: params.post_height,
        thumbscrew_head_d: params.thumbscrew_head_d,
        thumbscrew_clearance_d: params.thumbscrew_clearance_d,
        jig_size: params.jig_size,
        insert_height: params.insert_height,
        pcb_support_radius: params.pcb_support_radius,
        pcb_support_offset: params.pcb_support_offset,
    };
    let json_str = serde_json::to_string_pretty(&input)
        .map_err(|e| AppError::Other(format!("序列化参数失败: {}", e)))?;
    fs::write(&input_path, json_str).map_err(|e| AppError::Io(e.to_string()))?;

    // 调用 Python 脚本(传绝对路径,避免 working dir 问题)
    let ext = output_path
        .extension()
        .and_then(|s| s.to_str())
        .unwrap_or("stl");
    let output = timeout(
        Duration::from_secs(180),
        Command::new(python_path)
            .arg(script_path)
            .arg("--input")
            .arg(&input_path)
            .arg("--output")
            .arg(output_path)
            .arg("--part")
            .arg(part.to_str())
            .arg("--format")
            .arg(ext)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output(),
    )
    .await
    .map_err(|_| AppError::Timeout("Python 生成超时(180s)".into()))??;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).into_owned();
        let stdout = String::from_utf8_lossy(&output.stdout).into_owned();
        let mut detail = String::new();
        if !stderr.is_empty() {
            detail.push_str(&format!("stderr: {}", stderr));
        }
        if !stdout.is_empty() {
            detail.push_str(&format!("\nstdout: {}", stdout));
        }
        if detail.is_empty() {
            detail = format!(
                "exit code: {}",
                output.status.code().unwrap_or(-1)
            );
        }
        return Err(AppError::ScadFailed(format!(
            "Python 脚本失败: {}",
            detail
        )));
    }

    Ok(())
}

/// 获取项目根目录
/// tauri dev 时,cwd 在 src-tauri,所以用 CARGO_MANIFEST_DIR (编译期常量) 上溯一层
fn project_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .map(|p| p.to_path_buf())
        .unwrap_or_else(|| PathBuf::from("."))
}

/// 主入口:渲染单个部件为 STL 字节
pub async fn render_to_stl(
    configured_python: Option<&str>,
    params: &ScadParams,
    part: Part,
) -> Result<Vec<u8>, AppError> {
    let python = resolve_python(configured_python)
        .ok_or_else(|| AppError::OpenScadNotFound("未找到 Python。请先安装 Python 3.10+ 并 `pip install build123d shapely numpy`".into()))?;

    let script_path = project_root().join("python").join("jig_generator.py");
    if !script_path.exists() {
        return Err(AppError::Other(format!(
            "Python 脚本不存在: {}。请确认在项目根目录运行",
            script_path.display()
        )));
    }

    let work = work_dir()?;
    let output_stl = work.join("jig.stl");

    // 生成 + 读取包成一个结果;无论成功/失败/超时都清理工作目录(修复失败路径泄漏残留目录)
    let result: Result<Vec<u8>, AppError> = async {
        run_python(&python, params, part, &work, &output_stl, &script_path).await?;

        let mut file = tokio::fs::File::open(&output_stl)
            .await
            .map_err(|e| AppError::Io(format!("读取 STL 失败: {}", e)))?;
        let mut bytes = Vec::new();
        file.read_to_end(&mut bytes)
            .await
            .map_err(|e| AppError::Io(format!("读取 STL 失败: {}", e)))?;
        Ok(bytes)
    }
    .await;

    let _ = fs::remove_dir_all(&work);
    result
}

/// 把单个部件渲染到指定路径(给导出按钮用)
pub async fn render_to_file(
    configured_python: Option<&str>,
    params: &ScadParams,
    part: Part,
    output_path: &Path,
) -> Result<(), AppError> {
    let python = resolve_python(configured_python)
        .ok_or_else(|| AppError::OpenScadNotFound("未找到 Python".into()))?;

    let script_path = project_root().join("python").join("jig_generator.py");
    if !script_path.exists() {
        return Err(AppError::Other(format!(
            "Python 脚本不存在: {}。请确认在项目根目录运行",
            script_path.display()
        )));
    }

    let work = work_dir()?;
    let intermediate = work.join("jig.stl");

    // 同上:失败/超时也清理工作目录
    let result: Result<(), AppError> = async {
        run_python(&python, params, part, &work, &intermediate, &script_path).await?;
        fs::copy(&intermediate, output_path).map_err(|e| AppError::Io(e.to_string()))?;
        Ok(())
    }
    .await;

    let _ = fs::remove_dir_all(&work);
    result
}