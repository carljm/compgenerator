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
