import os
from glob import glob

from setuptools import find_packages, setup

package_name = "cognitive_language"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
        (os.path.join("share", package_name, "config"), glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Luis-Pena-Udit",
    maintainer_email="luis.penya@udit.es",
    description="Capa cognitiva de lenguaje (RAG + LLM) con la acción Think",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "cognitive_node = cognitive_language.think_server:main",
            "think_client = cognitive_language.think_client:main",
            "cognitive_cli = cognitive_language.cli:main",
        ],
    },
)
