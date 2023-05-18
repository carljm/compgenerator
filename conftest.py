def pytest_addoption(parser):
    parser.addoption(
        "--python",
        action="store",
        default="",
        help="path to Python executable to test (defaults to sys.executable)",
    )
    parser.addoption(
        "--logfile",
        action="store",
        default="",
        help="path to logfile for valid samples",
    )
    parser.addoption(
        "--port",
        action="store",
        default="",
        help="port to use for evalserver",
    )
    parser.addoption(
        "--run-evalserver",
        action="store_true",
        default=False,
        help="run evalserver from the test; if not set, "
        "evalserver must be started separately",
    )
