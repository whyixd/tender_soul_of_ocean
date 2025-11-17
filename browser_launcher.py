import asyncio
import os
import shutil
import subprocess
import webbrowser
from functools import partial
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor


class BrowserLauncher:
    """
    支援 asyncio 的瀏覽器啟動器
    可以非同步地開啟瀏覽器並跳轉到指定網址
    """

    _BROWSER_PROFILES: Dict[str, Dict[str, object]] = {
        "chrome": {
            "process_names": ["chrome.exe", "chrome"],
            "executable": "chrome.exe",
            "default_paths": [
                Path(path) / "Google" / "Chrome" / "Application" / "chrome.exe"
                for path in (
                    os.environ.get("PROGRAMFILES"),
                    os.environ.get("PROGRAMFILES(X86)"),
                    os.environ.get("LOCALAPPDATA"),
                )
                if path
            ],
            "modes": {
                "normal": ["--new-window", "{url}"],
                "fullscreen": ["--new-window", "{url}", "--start-fullscreen"],
                "kiosk": ["--kiosk", "{url}"],
            },
        },
        "edge": {
            "process_names": ["msedge.exe", "msedge"],
            "executable": "msedge.exe",
            "default_paths": [
                Path(path) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
                for path in (
                    os.environ.get("PROGRAMFILES"),
                    os.environ.get("PROGRAMFILES(X86)"),
                )
                if path
            ],
            "modes": {
                "normal": ["--new-window", "{url}"],
                "fullscreen": ["--new-window", "{url}", "--start-fullscreen"],
                "kiosk": ["--kiosk", "{url}", "--edge-kiosk-type=fullscreen"],
            },
        },
    }

    def __init__(
        self,
        executor: Optional[ThreadPoolExecutor] = None,
        default_browser: str = "chrome",
    ):
        """
        初始化瀏覽器啟動器
        
        Args:
            executor: 用於執行阻塞操作的執行緒池，如為 None 則使用預設執行器
            default_browser: 當未指定瀏覽器時使用的瀏覽器別名
        """
        self.executor = executor
        self.default_browser = default_browser.lower()

    async def open_url(self, url: str) -> bool:
        """
        非同步開啟指定網址
        
        Args:
            url: 要開啟的網址
            
        Returns:
            bool: 成功回傳 True，失敗回傳 False
        """
        loop = asyncio.get_event_loop()
        try:
            # 在線程池中執行阻塞的 webbrowser 操作
            result = await loop.run_in_executor(
                self.executor,
                webbrowser.open,
                url
            )
            return result
        except Exception as e:
            print(f"開啟瀏覽器失敗: {e}")
            return False

    async def open_url_with_browser(
        self,
        url: str,
        browser: Optional[str] = None,
        *,
        mode: str = "normal",
        relaunch: bool = True,
        browser_path: Optional[str] = None,
        kill_timeout: float = 5.0,
    ) -> bool:
        """
        非同步開啟指定網址，可指定瀏覽器類型
        
        Args:
            url: 要開啟的網址
            browser: 瀏覽器類型別名 (如 'chrome', 'edge' 等)，為 None 則使用預設瀏覽器
            mode: 瀏覽器啟動模式，可選 normal/fullscreen/kiosk
            relaunch: 是否在啟動前先關閉已執行的同類瀏覽器實例
            browser_path: 自訂瀏覽器執行路徑，留空則按預設路徑查找
            kill_timeout: 在嘗試關閉瀏覽器後等待其退出的最長秒數
            
        Returns:
            bool: 成功回傳 True，失敗回傳 False
        """
        loop = asyncio.get_event_loop()
        try:
            profile = self._resolve_browser_profile(browser)

            if relaunch:
                await self._ensure_browser_closed(profile["process_names"], timeout=kill_timeout)

            launch_func = partial(
                self._launch_browser,
                profile,
                url,
                mode,
                browser_path,
            )
            return await loop.run_in_executor(self.executor, launch_func)
        except Exception as e:
            print(f"開啟瀏覽器失敗: {e}")
            return False

    async def open_multiple_urls(self, urls: list) -> dict:
        """
        非同步開啟多個網址
        
        Args:
            urls: 網址列表
            
        Returns:
            dict: 每個網址的開啟結果 {'url': bool}
        """
        tasks = [self.open_url(url) for url in urls]
        results = await asyncio.gather(*tasks)
        return dict(zip(urls, results))

    def _resolve_browser_profile(self, browser: Optional[str]) -> Dict[str, object]:
        browser_key = (browser or self.default_browser).lower()
        if browser_key not in self._BROWSER_PROFILES:
            raise ValueError(f"不支援的瀏覽器類型: {browser_key}")
        return self._BROWSER_PROFILES[browser_key]

    async def _ensure_browser_closed(self, process_names: List[str], timeout: float) -> None:
        if not process_names:
            return

        if await asyncio.to_thread(self._is_browser_running, process_names):
            await asyncio.to_thread(self._terminate_processes, process_names)
            await self._wait_for_shutdown(process_names, timeout)

    async def _wait_for_shutdown(self, process_names: List[str], timeout: float) -> None:
        deadline = asyncio.get_running_loop().time() + timeout
        while await asyncio.to_thread(self._is_browser_running, process_names):
            if asyncio.get_running_loop().time() >= deadline:
                break
            await asyncio.sleep(0.2)

    def _is_browser_running(self, process_names: List[str]) -> bool:
        for name in process_names:
            if not name:
                continue

            if os.name == "nt":
                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {name}"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if name.lower() in result.stdout.lower():
                    return True
            else:
                result = subprocess.run(
                    ["pgrep", "-f", name],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    return True
        return False

    def _terminate_processes(self, process_names: List[str]) -> None:
        for name in process_names:
            if not name:
                continue

            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/IM", name, "/F"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            else:
                subprocess.run(
                    ["pkill", "-f", name],
                    capture_output=True,
                    text=True,
                    check=False,
                )

    def _launch_browser(
        self,
        profile: Dict[str, object],
        url: str,
        mode: str,
        browser_path: Optional[str],
    ) -> bool:
        normalized_mode = mode.lower()
        mode_args = profile["modes"].get(normalized_mode)
        if mode_args is None:
            raise ValueError(f"不支援的啟動模式: {mode}")

        executable = self._locate_executable(profile, browser_path)
        args = [executable] + [arg.format(url=url) for arg in mode_args]

        subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True

    def _locate_executable(
        self,
        profile: Dict[str, object],
        browser_path: Optional[str],
    ) -> str:
        if browser_path:
            candidate = Path(browser_path)
            if not candidate.is_file():
                raise FileNotFoundError(f"找不到指定的瀏覽器路徑: {browser_path}")
            return str(candidate)

        exe_name = profile["executable"]
        located = shutil.which(exe_name)
        if located:
            return located

        for candidate in profile.get("default_paths", []):
            if candidate.is_file():
                return str(candidate)

        raise FileNotFoundError(f"無法定位瀏覽器執行檔: {exe_name}")


# 使用示例
# async def main():
#     launcher = BrowserLauncher()

#     # 以 kiosk 模式重新啟動指定瀏覽器並開啟網址
#     success = await launcher.open_url_with_browser(
#         "https://www.google.com",
#         browser="chrome",
#         mode="kiosk",
#     )
#     print(f"開啟網址結果: {success}")



# if __name__ == "__main__":
#     asyncio.run(main())
