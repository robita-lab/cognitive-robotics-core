from setuptools import find_packages, setup

package_name = 'speech_to_text'

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
            'doa_publisher = speech_to_text.doa_publisher:main',
            'listener = speech_to_text.doa_subscriber:main',
            'stt_publisher = speech_to_text.stt_publisher:main',
            'stt_subscriber = speech_to_text.stt_subscriber:main'
        ],
    },
)
