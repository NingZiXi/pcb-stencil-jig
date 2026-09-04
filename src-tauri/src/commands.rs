//! Tauri IPC 命令入口
use crate::error::AppError;
use crate::openscad_detect;
use crate::scad;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use tauri::AppHandle;
use tauri_plugin_store::StoreExt;

/// 与前端 TS 类型保持一致的参数结构
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScadParams {
    pub pcb_size_x: f64,
    pub pcb_size_y: f64,
    pub pcb_thickness: f64,
    pub pcb_pocket_clearance: f64,
    /// PCB 板框多边形点 [[x, y], ...],已居中(以 bbox 中心为原点)
    /// 空数组 = 用矩形代替(向后兼容)
    #[serde(default)]
    pub pcb_outline_points: Vec<[f64; 2]>,
    /// PCB 板框内孔轮廓 [[[x, y], ...], ...],同 pcb_outline_points 坐标系
    /// 空数组 = 无内孔
    #[serde(default)]
    pub pcb_outline_holes: Vec<Vec<[f64; 2]>>,
    pub stencil_size: f64,
    pub screw_spacing: f64,
    pub base_height: f64,
    pub top_cover_height: f64,
    pub post_diameter: f64,
    pub post_height: f64,
    pub thumbscrew_head_d: f64,
    pub thumbscrew_clearance_d: f64,
    pub jig_size: f64,
    #[serde(default = "default_insert_height")]
    pub insert_height: f64,
    #[serde(default = "default_support_radius")]
    pub pcb_support_radius: f64,
    #[serde(default = "default_support_offset")]
    pub pcb_support_offset: f64,
}

fn default_insert_height() -> f64 { 8.0 }
fn default_support_radius() -> f64 { 5.0 }
fn default_support_offset() -> f64 { 58.0 }

/// 部件标识
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Part {
    Base,
    PcbInsert,
    TopCover,
}

impl Part {
    pub fn to_str(&self) -> &'static str {
        match self {
            Part::Base => "base",
            Part::PcbInsert => "insert",
            Part::TopCover => "cover",
        }
    }
}

const STORE_FILE: &str = "settings.json";
const KEY_PYTHON_PATH: &str = "python_path";

// ---------------------------------------------------------------------------
// 引擎状态与一键配置
// ---------------------------------------------------------------------------

/// 引擎(Python + CAD 依赖)状态
#[derive(Debug, Clone, Serialize)]
pub struct EngineStatus {
    /// 找到的 python.exe 路径(None = 未找到)
    pub python_path: Option<String>,
    /// CAD 依赖(build123d/shapely/numpy)是否齐全
    pub deps_ok: bool,
    /// 缺失的依赖名列表
    pub missing: Vec<String>,
    /// 是否使用随应用打包的内置引擎
    pub bundled: bool,
}

/// 用 find_spec 检查依赖(只查不导入,秒回;真 import build123d 要 ~5s)
fn check_deps_blocking(python: &str) -> Vec<String> {
    const REQUIRED: &[&str] = &["build123d", "shapely", "numpy"];
    let script = format!(
        "import importlib.util,sys;\
         missing=[m for m in {REQUIRED:?} if importlib.util.find_spec(m) is None];\
         print(','.join(missing))"
    );
    match std::process::Command::new(python)
        .arg("-c")
        .arg(&script)
        .output()
    {
        Ok(out) if out.status.success() => {
            let text = String::from_utf8_lossy(&out.stdout).trim().to_string();
            if text.is_empty() {
                Vec::new()
            } else {
                text.split(',').map(|s| s.to_string()).collect()
            }
        }
        // python 本身跑不起来(损坏/版本过老):全部视为缺失
        _ => REQUIRED.iter().map(|s| s.to_string()).collect(),
    }
}

/// 查询引擎状态:用户配置 > 内置引擎 > 系统搜索;找到 python 后检查依赖
#[tauri::command]
pub async fn get_engine_status(app: AppHandle) -> Result<EngineStatus, AppError> {
    let configured = app
        .store(STORE_FILE)
        .ok()
        .and_then(|s| s.get(KEY_PYTHON_PATH))
        .and_then(|v| v.as_str().map(String::from))
        .filter(|s| !s.is_empty() && std::path::Path::new(s).exists());

    let bundled = scad::bundled_python(Some(&app));

    // 优先级与生成路径一致:用户配置 > 内置 > 系统
    let python = configured
        .clone()
        .or_else(|| bundled.clone())
        .or_else(openscad_detect::detect_python);
    let using_bundled = configured.is_none() && python == bundled && bundled.is_some();

    match python {
        Some(p) => {
            let py = p.clone();
            let missing = tokio::task::spawn_blocking(move || check_deps_blocking(&py))
                .await
                .map_err(|e| AppError::Other(format!("依赖检查失败: {}", e)))?;
            Ok(EngineStatus {
                python_path: Some(p),
                deps_ok: missing.is_empty(),
                missing,
                bundled: using_bundled,
            })
        }
        None => Ok(EngineStatus {
            python_path: None,
            deps_ok: false,
            missing: Vec::new(),
            bundled: false,
        }),
    }
}

/// 逐行读取子进程输出并 emit 到前端;返回是否退出成功
async fn run_with_log(app: &AppHandle, mut cmd: std::process::Command) -> Result<(), AppError> {
    use std::io::{BufRead, BufReader};
    use std::process::Stdio;
    use tauri::Emitter;

    cmd.stdout(Stdio::piped()).stderr(Stdio::piped());
    let mut child = cmd
        .spawn()
        .map_err(|e| AppError::Io(format!("启动安装进程失败: {}", e)))?;

    let stdout = child.stdout.take().unwrap();
    let stderr = child.stderr.take().unwrap();

    let h_stdout = app.clone();
    let t_out = tokio::task::spawn_blocking(move || {
        for line in BufReader::new(stdout).lines().map_while(Result::ok) {
            let _ = h_stdout.emit("install-log", line);
        }
    });
    let h_err = app.clone();
    let t_err = tokio::task::spawn_blocking(move || {
        for line in BufReader::new(stderr).lines().map_while(Result::ok) {
            let _ = h_err.emit("install-log", line);
        }
    });

    let _ = t_out.await;
    let _ = t_err.await;

    let status = tokio::time::timeout(
        std::time::Duration::from_secs(600),
        tokio::task::spawn_blocking(move || child.wait()),
    )
    .await
    .map_err(|_| {
        let _ = app.emit("install-log", "[timeout] 安装超时(10 分钟),请检查网络后重试");
        AppError::Timeout("安装超时(10 分钟)".into())
    })?
    .map_err(|e| AppError::Io(format!("等待安装进程失败: {}", e)))?
    .map_err(|e| AppError::Io(format!("安装进程异常: {}", e)))?;

    if status.success() {
        Ok(())
    } else {
        Err(AppError::ScadFailed(format!(
            "安装进程退出码 {:?},详见日志输出",
            status.code()
        )))
    }
}

/// 一键安装 CAD 依赖(pip,走清华镜像;--progress-bar off 输出干净的行流)
#[tauri::command]
pub async fn install_deps(
    app: AppHandle,
    python_path: String,
) -> Result<(), AppError> {
    use tauri::Emitter;
    if !std::path::Path::new(&python_path).exists() {
        return Err(AppError::Other(format!("路径不存在: {}", python_path)));
    }
    let _ = app.emit("install-log", format!("> pip install build123d shapely numpy(清华镜像)"));

    let mut cmd = std::process::Command::new(&python_path);
    cmd.arg("-m")
        .arg("pip")
        .arg("install")
        .arg("--no-input")
        .arg("--progress-bar")
        .arg("off")
        .arg("-i")
        .arg("https://pypi.tuna.tsinghua.edu.cn/simple")
        .arg("build123d")
        .arg("shapely")
        .arg("numpy");

    run_with_log(&app, cmd).await
}

/// 一键安装 Python(winget 静默安装 3.12);成功后返回新装的 python 路径
#[tauri::command]
pub async fn install_python(app: AppHandle) -> Result<String, AppError> {
    use tauri::Emitter;
    let _ = app.emit("install-log", "> winget install Python.Python.3.12(静默安装)");

    let mut cmd = std::process::Command::new("winget");
    cmd.arg("install")
        .arg("--id").arg("Python.Python.3.12")
        .arg("-e")
        .arg("--silent")
        .arg("--disable-interactivity")
        .arg("--accept-source-agreements")
        .arg("--accept-package-agreements");

    run_with_log(&app, cmd).await?;

    // winget 装完 PATH 不一定对当前进程刷新:直接扫安装目录
    tokio::time::sleep(std::time::Duration::from_secs(2)).await; // 等文件落盘
    let found = openscad_detect::find_python_in_localappdata()
        .or_else(openscad_detect::find_python_in_path)
        .ok_or_else(|| {
            AppError::Other(
                "winget 安装完成但未找到 python.exe,请手动选择安装位置".into(),
            )
        })?;
    Ok(found)
}

/// 用户手动设置 Python 路径,持久化到 store
/// 自动把 Git Bash 风格路径(/c/...)转成 Windows 原生路径
#[tauri::command]
pub async fn set_python_path(app: AppHandle, path: String) -> Result<String, AppError> {
    use crate::openscad_detect;

    // 路径归化(Git Bash → Windows)
    let normalized = openscad_detect::normalize_path(&path);

    // 验证文件存在(尝试多个变体)
    let candidates = [
        normalized.clone(),
        path.clone(),
        // 也试试加 .exe 后缀
        format!("{}.exe", normalized.trim_end_matches(".exe")),
    ];
    let actual = candidates
        .iter()
        .find(|p| !p.is_empty() && std::path::Path::new(p).exists())
        .ok_or_else(|| AppError::Other(format!("路径不存在: {}", path)))?
        .clone();

    let store = app
        .store(STORE_FILE)
        .map_err(|e| AppError::Other(format!("打开设置文件失败: {}", e)))?;

    store.set(KEY_PYTHON_PATH, serde_json::Value::String(actual.clone()));
    store
        .save()
        .map_err(|e| AppError::Other(format!("保存设置失败: {}", e)))?;

    Ok(actual)
}

/// 渲染单个部件为 STL,返回字节数组(供前端预览)
#[tauri::command]
pub async fn generate_stl(
    app: AppHandle,
    params: ScadParams,
    part: Part,
) -> Result<Vec<u8>, AppError> {
    let configured = app
        .store(STORE_FILE)
        .ok()
        .and_then(|s| s.get(KEY_PYTHON_PATH))
        .and_then(|v| v.as_str().map(String::from))
        .filter(|s| !s.is_empty());

    scad::render_to_stl(&app, configured.as_deref(), &params, part).await
}

/// 把单个部件渲染到指定路径(供前端导出 STL 文件)
#[tauri::command]
pub async fn export_stl(
    app: AppHandle,
    params: ScadParams,
    part: Part,
    output_path: String,
) -> Result<String, AppError> {
    let configured = app
        .store(STORE_FILE)
        .ok()
        .and_then(|s| s.get(KEY_PYTHON_PATH))
        .and_then(|v| v.as_str().map(String::from))
        .filter(|s| !s.is_empty());

    let path = PathBuf::from(&output_path);
    scad::render_to_file(&app, configured.as_deref(), &params, part, &path).await?;
    Ok(output_path)
}

/// 把字节写入指定路径(供前端把缓存的 STL bytes 直接落盘,避免重复生成)
#[tauri::command]
pub async fn write_file_bytes(path: String, bytes: Vec<u8>) -> Result<(), AppError> {
    std::fs::write(&path, bytes)
        .map_err(|e| AppError::Io(format!("写入文件失败 {}: {}", path, e)))
}

/// 项目文件 schema
#[derive(Debug, Serialize, Deserialize)]
pub struct ProjectFile {
    #[serde(default = "default_version")]
    pub version: u32,
    pub config: ScadParams,
    #[serde(default)]
    pub gerber_filename: Option<String>,
    #[serde(default)]
    pub created_at: String,
    #[serde(default)]
    pub updated_at: String,
}

fn default_version() -> u32 {
    1
}

/// 保存项目配置到 JSON 文件
#[tauri::command]
pub async fn save_project(
    path: String,
    config: ScadParams,
    gerber_filename: Option<String>,
) -> Result<String, AppError> {
    let now = chrono_like_now();
    let project = ProjectFile {
        version: 1,
        config,
        gerber_filename,
        created_at: now.clone(),
        updated_at: now,
    };

    let json = serde_json::to_string_pretty(&project)
        .map_err(|e| AppError::Other(format!("序列化失败: {}", e)))?;
    std::fs::write(&path, json).map_err(|e| AppError::Io(e.to_string()))?;
    Ok(path)
}

/// 加载项目配置文件
#[tauri::command]
pub async fn load_project(path: String) -> Result<ProjectFile, AppError> {
    let text = std::fs::read_to_string(&path).map_err(|e| AppError::Io(e.to_string()))?;
    let project: ProjectFile = serde_json::from_str(&text)
        .map_err(|e| AppError::Other(format!("JSON 解析失败: {}", e)))?;
    Ok(project)
}

/// 读取拖入的文件,供 drag-drop 后使用
#[tauri::command]
pub async fn read_dropped_file(path: String) -> Result<Vec<u8>, AppError> {
    let bytes = std::fs::read(&path).map_err(|e| AppError::Io(format!("读取文件失败 {}: {}", path, e)))?;
    Ok(bytes)
}

/// 简易 ISO 8601 时间戳(避免引入 chrono 依赖)
fn chrono_like_now() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let now = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default();
    format!("epoch:{}", now.as_secs())
}