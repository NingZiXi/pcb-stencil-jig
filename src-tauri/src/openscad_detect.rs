//! 多策略探测 Python 和 OpenSCAD 可执行文件
//!
//! Python 是夹具生成的 CAD 引擎(通过 python/jig_generator.py)
//! OpenSCAD 是历史遗留的备选引擎
use std::path::Path;
use std::process::Command;

#[cfg(target_os = "windows")]
const PYTHON_PATHS: &[&str] = &[
    "C:/Espressif/tools/python/python.exe",
    "C:/Python311/python.exe",
    "C:/Python312/python.exe",
    "C:/Python313/python.exe",
    "C:/Users/Administrator/AppData/Local/Programs/Python/Python311/python.exe",
    "C:/Program Files/Python311/python.exe",
];

#[cfg(target_os = "macos")]
const PYTHON_PATHS: &[&str] = &[
    "/opt/homebrew/bin/python3",
    "/usr/local/bin/python3",
    "/Library/Frameworks/Python.framework/Versions/Current/bin/python3",
];

#[cfg(all(unix, not(target_os = "macos")))]
const PYTHON_PATHS: &[&str] = &[
    "/usr/bin/python3",
    "/usr/local/bin/python3",
    "/opt/python/bin/python3",
];

/// 通过系统 PATH 查找 Python
/// Windows: 用 `where`(返回 C:\... 原 原路径)
/// Unix: 用 `which`(返回 /usr/bin/... 原 原路径)
pub fn find_python_in_path() -> Option<String> {
    let lookup = if cfg!(target_os = "windows") { "where" } else { "which" };

    for cmd in &["python", "python3", "py"] {
        if let Ok(output) = Command::new(lookup).arg(cmd).output() {
            if !output.status.success() {
                continue;
            }
            let stdout = String::from_utf8_lossy(&output.stdout);
            for line in stdout.lines() {
                let raw = line.trim();
                if raw.is_empty() {
                    continue;
                }
                // Git Bash 风格转 Windows 原生路径: /c/Espressif/... → C:\Espressif\...
                let path_str = normalize_path(raw);
                if !path_str.is_empty() && Path::new(&path_str).exists() {
                    return Some(path_str);
                }
            }
        }
    }
    None
}

/// 路径归化(公开函数)
/// - /c/Espressif/... → C:\Espressif\...
/// - /usr/bin/python3 → /usr/bin/python3 (Unix 原样)
/// - C:\Path\... → C:\Path\... (Windows 原样)
pub fn normalize_path(p: &str) -> String {
    // Git Bash 风格:/X/... 其中 X 是单个字母
    if cfg!(target_os = "windows") && p.starts_with('/') && p.len() > 2 {
        let chars: Vec<char> = p.chars().collect();
        if chars.len() >= 3 && chars[2] == '/' {
            let drive = chars[1].to_ascii_uppercase();
            let rest = &p[3..];
            // 把 / 转成 \
            let rest_win = rest.replace('/', "\\");
            return format!("{}:\\{}", drive, rest_win);
        }
    }
    p.to_string()
}

/// 在常见安装位置查找 Python
pub fn find_python_in_standard_paths() -> Option<String> {
    for path in PYTHON_PATHS {
        if Path::new(path).exists() {
            return Some(path.to_string());
        }
    }
    None
}

/// 综合探测 Python
pub fn detect_python() -> Option<String> {
    find_python_in_path().or_else(find_python_in_standard_paths)
}