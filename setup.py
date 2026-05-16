from setuptools import setup
from setuptools import find_packages
from setuptools.command.install import install
import os
import glob

package_name = 'l2cs_gaze_perception'

WRAPPER_SCRIPT = '''#!/usr/bin/python3
import sys
try:
    from importlib.metadata import distribution, PackageNotFoundError
except ImportError:
    try:
        from importlib_metadata import distribution, PackageNotFoundError
    except ImportError:
        from pkg_resources import load_entry_point
        def importlib_load_entry_point(spec, group, name):
            return load_entry_point(spec, group, name)

def importlib_load_entry_point(spec, group, name):
    dist_name, _, _ = spec.partition('==')
    try:
        matches = (
            entry_point
            for entry_point in distribution(dist_name).entry_points
            if entry_point.group == group and entry_point.name == name
        )
        return next(matches).load()
    except (PackageNotFoundError, StopIteration):
        from gaze.gaze_node import main
        return main

if __name__ == '__main__':
    sys.argv[0] = sys.argv[0].replace('-script.py', '').replace('.exe', '')
    load_entry_point = importlib_load_entry_point
    sys.exit(load_entry_point('{package_name}=={version}', 'console_scripts', 'gaze_node')())
'''


class CustomInstall(install):
    def run(self):
        install.run(self)
        # Patch entry point scripts to handle missing .dist-info
        install_dir = os.path.join(self.install_scripts, '')
        for script in glob.glob(os.path.join(install_dir, 'gaze_node*')):
            with open(script, 'w') as f:
                f.write(WRAPPER_SCRIPT.format(
                    package_name=package_name,
                    version='0.0.1',
                ))
            os.chmod(script, 0o755)


setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/gaze_pipeline.launch.py']),
        ('share/' + package_name + '/config', ['config/gaze_params.yaml']),
        ('share/' + package_name + '/models', ['models/L2CSNet_gaze360.pkl']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='user',
    maintainer_email='user@todo.todo',
    description='Webcam-based gaze estimation using L2CS-Net for ROS2 Humble',
    license='MIT',
    cmdclass={'install': CustomInstall},
    entry_points={
        'console_scripts': [
            'gaze_node = gaze.gaze_node:main',
        ],
    },
)
