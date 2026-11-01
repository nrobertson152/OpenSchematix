import pytest
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    yield
    env = item.funcargs.get("scene") or item.funcargs.get("env")
    if env:
        app = env[1]; cv = app.canvas
        print(f"\n[size] {item.name[:50]} canvas={cv.winfo_width()}x{cv.winfo_height()} mapped={cv.winfo_ismapped()} root={app.root.geometry()}")
