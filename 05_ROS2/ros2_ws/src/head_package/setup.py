from setuptools import find_packages, setup

package_name = 'head_package'

setup(
    name=package_name,
    version='0.0.0',
#    packages=find_packages(exclude=['test']),
    packages=find_packages(),
#    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='udito',
    maintainer_email='dartecne@gmail.com',
    description='Manejador de la cabeza de UDITO',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'head_server = head_package.head_service:main',
            'client = head_package.minimal_client:main',
            'talker = head_package.publisher_member_function:main',
            'listener = head_package.subscriber_member_function:main'
        ],
    },
)
