from setuptools import setup

setup(
    name="keytracker",
    version="0.1dev",
    packages=["keytracker"],
    install_requires=["requests", "mysqlclient", "Flask-SQLAlchemy"],
    license="GNU General Public License v3.0",
    long_description=open("README.md").read(),
)
