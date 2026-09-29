"""PureBrowser 端到端测试：验证 H.264 真的在。

用法: python tools/e2e_test.py

原理：启动一个 QWebEngineView，加载本地 HTML，
用 canPlayType 检测 avc1 是否被浏览器识别。
返回 "probably" 或 "maybe" 说明 H.264 可用。
"""
import sys
from pathlib import Path

HTML = """
<html><body><script>
const v = document.createElement('video');
const r = {
    avc1: v.canPlayType('video/mp4; codecs="avc1.42E01E"'),
    av01: v.canPlayType('video/mp4; codecs="av01.0.04M.08"'),
    vp9:  v.canPlayType('video/webm; codecs="vp9"'),
    mp4:  v.canPlayType('video/mp4'),
};
window.__result = JSON.stringify(r);
</script></body></html>
"""


def main() -> int:
    from PyQt6.QtCore import QUrl, QTimer
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtWebEngineCore import QWebEnginePage
    from PyQt6.QtWebEngineWidgets import QWebEngineView

    app = QApplication(sys.argv)
    view = QWebEngineView()
    view.resize(400, 300)
    view.show()

    result_holder = {"value": None}

    def on_load(ok):
        if not ok:
            print("[FAIL] 页面加载失败")
            app.exit(1)
            return

        def got(value):
            result_holder["value"] = value
            app.quit()

        view.page().runJavaScript("window.__result", got)

    view.loadFinished.connect(on_load)
    view.setHtml(HTML)

    # 超时保护
    QTimer.singleShot(15000, app.quit)

    app.exec()

    import json
    raw = result_holder["value"]
    if not raw:
        print("[FAIL] 未取回检测结果（超时或 JS 未执行）")
        return 1

    r = json.loads(raw)
    print("=" * 50)
    print("H.264 / 编解码器检测")
    print("=" * 50)
    for k, v in r.items():
        print(f"  {k:6s} : {v or '(不支持)'}")
    print("=" * 50)

    avc1 = r.get("avc1", "")
    if avc1 in ("probably", "maybe"):
        print(f"[OK]   H.264 可用（avc1 = {avc1}）")
        return 0
    else:
        print("[FAIL] H.264 不可用。自编译 QtWebEngine 可能被污染或依赖缺失。")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())