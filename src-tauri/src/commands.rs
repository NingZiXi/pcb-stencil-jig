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

/// 探测系统中是否安装 Python
/// 优先级:用户配置路径 → PATH → 标准安装位置
#[tauri::command]
pub async fn detect_python(app: AppHandle) -> Result<String, AppError> {
    // 1. 先查用户配置
    if let Ok(store) = app.store(STORE_FILE) {
        if let Some(path_value) = store.get(KEY_PYTHON_PATH) {
            if let Some(path_str) = path_value.as_str() {
                if !path_str.is_empty() {
                    let normalized = openscad_detect::normalize_path(path_str);
                    if std::path::Path::new(&normalized).exists() {
                        // 如果归化后不同,回写到 store
                        if normalized != path_str {
                            store.set(
                                KEY_PYTHON_PATH,
                                serde_json::Value::String(normalized.clone()),
                            );
                            let _ = store.save();
                        }
                        return Ok(normalized);
                    }
                }
            }
        }
    }

    // 2. PATH / 标准路径探测
    openscad_detect::detect_python().ok_or_else(|| {
        AppError::OpenScadNotFound(
            "未找到 Python。请先安装 Python 3.10+,然后 `pip install build123d shapely numpy`,最后在下方手动指定 python.exe 路径。".into(),
        )
    })
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

    scad::render_to_stl(configured.as_deref(), &params, part).await
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
    scad::render_to_file(configured.as_deref(), &params, part, &path).await?;
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