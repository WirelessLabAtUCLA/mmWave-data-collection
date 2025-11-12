from setuptools import setup, find_packages
import os
from glob import glob

package_name = 'mmwave_collection'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
        (os.path.join('share', package_name, 'config'), glob('../../config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='User',
    maintainer_email='user@example.com',
    description='mmWave data collection system',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'router_node = mmwave_collection.nodes.router_node:main',
            'gps_node = mmwave_collection.nodes.gps_node:main',
            'camera_node = mmwave_collection.nodes.camera_node:main',
            'sync_node = mmwave_collection.nodes.sync_node:main',
            'rotation_table_node = mmwave_collection.nodes.rotation_table_node:main',
            'automated_collection_node = mmwave_collection.nodes.automated_collection_node:main',
        ],
    },
)

