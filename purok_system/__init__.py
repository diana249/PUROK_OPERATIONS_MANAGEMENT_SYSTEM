try:
    import pymysql
except Exception:
    pymysql = None

if pymysql is not None:
    pymysql.version_info = (2, 2, 1, "final", 0)
    pymysql.__version__ = "2.2.1"
    pymysql.install_as_MySQLdb()
