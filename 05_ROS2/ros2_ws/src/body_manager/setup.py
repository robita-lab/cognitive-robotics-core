from setuptools import find_packages, setup

package_name = 'body_manager'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='udito',
    maintainer_email='dartecne@gmail.com',
    description='TODO: Package description',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'idle_behavior = body_manager.idle:main',
            'gaze_by_lidar_behavior = body_manager.gaze_by_lidar:main', 
            'gaze_behavior = body_manager.gaze:main',
            'introduce_myself_behavior = body_manager.introduce_myself:main',
            'sequencer = body_manager.sequencer:main'
        ],
    },
)
