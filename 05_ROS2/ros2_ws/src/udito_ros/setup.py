import os
from glob import glob

from setuptools import setup

package_name = "udito_ros"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
        (os.path.join("share", package_name, "config"), glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Danilo Guevara",
    maintainer_email="danilo.guevara@gmail.com",
    description="Arquitectura 3T - UDITO sobre ROS 2",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "stt_node = udito_ros.stt_node:main",
            "tts_node = udito_ros.tts_node:main",
            "orchestrator_node = udito_ros.orchestrator_node:main",
            "cognitive_node = udito_ros.cognitive_node:main",
            "console_node = udito_ros.console_node:main",
            "body_example_node = udito_ros.body_example_node:main",
        ],
    },
)
