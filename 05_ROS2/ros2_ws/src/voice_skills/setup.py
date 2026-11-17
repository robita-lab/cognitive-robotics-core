from setuptools import setup

package_name = "voice_skills"

setup(
    name=package_name,
    version="0.2.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Danilo Guevara",
    maintainer_email="dguevaras@hotmail.com",
    description="Arquitectura híbrida - UDITO · Habilidades de voz (STT y TTS)",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "stt_node = voice_skills.stt_node:main",
            "tts_node = voice_skills.tts_node:main",
        ],
    },
)
