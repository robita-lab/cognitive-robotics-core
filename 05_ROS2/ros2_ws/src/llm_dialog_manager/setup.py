import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'llm_dialog_manager'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
            glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools', 'httpx>=0.27'],
    zip_safe=True,
    maintainer='Luis-Pena-Udit',
    maintainer_email='luis.penya@udit.es',
    description='Local-first dialog manager: routes turns between an on-robot LLM tier '
                'and a GPU server tier.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'llm_dialog_manager = llm_dialog_manager.node:main',
            'llm_dialog_cli = llm_dialog_manager.cli:main',
            'mock_com_act_server = llm_dialog_manager.mock_comact:main',
        ],
    },
)
