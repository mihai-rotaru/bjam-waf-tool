#! /usr/bin/env python
# per rosengren 2011

from os import sep, name
from os.path import abspath
from waflib import Logs
from waflib.TaskGen import feature, after_method
from waflib.Task import Task, always_run

# from boost source code:
def _get_bjam_build_dir():
    import os
    if os.name == 'nt':
        return "bin.ntx86"
    elif (os.name == 'posix') and os.__dict__.has_key('uname'):
        if os.uname()[0].lower().startswith('cygwin'):
            return "bin.cygwinx86"
            if 'TMP' in os.environ and os.environ['TMP'].find('~') != -1:
                print 'Setting $TMP to /tmp to get around problem with short path names'
                os.environ['TMP'] = '/tmp'
        elif os.uname()[0] == 'Linux':
            cpu = os.uname()[4]
            if re.match("i.86", cpu):
                return "bin.linuxx86";
            else:
                return "bin.linux" + os.uname()[4]
        elif os.uname()[0] == 'SunOS':
            return "bin.solaris"
        elif os.uname()[0] == 'Darwin':
            if os.uname()[4] == 'i386':
                return "bin.macosxx86"
            else:
                return "bin.macosxppc"
        elif os.uname()[0] == "AIX":
            return "bin.aix"
        elif os.uname()[0] == "IRIX64":
            return "bin.irix"
        elif os.uname()[0] == "FreeBSD":
            return "bin.freebsd"
        elif os.uname()[0] == "OSF1":
            return "bin.osf"
        else:
            Logs.warn( "Don't know directory where Jam is built for this system: " + os.name + "/" + os.uname()[0] )
            return None
    else:
        Logs.warn( "Don't know directory where Jam is built for this system: " + os.name )
        return None

def options(opt):
    grp = opt.add_option_group('Bjam Options')
    grp.add_option('--bjam_src', default=None, help='You can find it in <boost root>/tools/build/v2')
    grp.add_option('--bjam_uname', default=_get_bjam_build_dir(), help='bjam is built in <src>/engine/<uname>')
    grp.add_option('--bjam_config', default=None)
    grp.add_option('--bjam_toolset', default=None)

def configure(cnf):
    if not cnf.env.BJAM_SRC:
        cnf.env.BJAM_SRC = cnf.options.bjam_src
    if not cnf.env.BJAM_UNAME:
        cnf.env.BJAM_UNAME = cnf.options.bjam_uname
    try:
        cnf.find_program('bjam', path_list=[
            cnf.env.BJAM_SRC + sep + 'engine' + sep + cnf.env.BJAM_UNAME
        ])
    except Exception as e:
        cnf.env.BJAM = None
    if not cnf.env.BJAM_CONFIG:
        cnf.env.BJAM_CONFIG = cnf.options.bjam_config
    if not cnf.env.BJAM_TOOLSET:
        cnf.env.BJAM_TOOLSET = cnf.options.bjam_toolset

@feature('bjam')
@after_method('process_rule')
def process_bjam(self):
    if not self.bld.env.BJAM:
        self.create_task('bjam_creator')
    self.create_task('bjam_build')
    self.create_task('bjam_installer')
    if getattr(self, 'always', False):
        always_run(bjam_creator)
        always_run(bjam_build)
    always_run(bjam_installer)

class bjam_creator(Task):
    ext_out = 'bjam_exe'
    before = ['bjam_build', 'cxxprogram' ]
    vars=['BJAM_SRC', 'BJAM_UNAME']
    def run(self):
        env = self.env
        gen = self.generator
        path = gen.path
        bld = gen.bld
        if not env.BJAM_SRC:
            Logs.error('bjam needs to be built; please re-configure the project providing the location of bjam sources with the --bjam_src option.')
            return -1
        bjam = ''
        try:
            bjam = gen.bld.root.find_dir(env.BJAM_SRC)
        except:
            Logs.error( 'Cannot find folder: %s' % env.BJAM_SRC )
            return -1
        if not bjam:
            Logs.error('Can not find bjam source')
            return -1
        if not bjam.find_resource( 'bootstrap.bat' ) and bjam.find_resource( 'bootstrap.sh' ):
            Logs.error( 'bjam source folder must contain bootstrap.bat and bootstrap.sh, please make sure to provide the correct folder with the --bjam_src option.' )
            return -1
        if name == 'nt':
            bjam_cmd = ['cmd', '/c', 'bootstrap.bat']
            bjam_exe_name = 'bjam.exe'
        else:
            bjam_cmd = ['bootstrap.sh']
            bjam_exe_name = 'bjam'
        Logs.warn( 'Building bjam: %s' % str(bjam_cmd) )
        result = self.exec_command(bjam_cmd, cwd=bjam.abspath())
        if not( result == 0 ):
            Logs.error('bjam bootstrap failed (non-zero return value)')
            return -1
        bjam_exe = bjam.find_resource( 'engine/' + env.BJAM_UNAME + '/' + bjam_exe_name )
        if bjam_exe:
            env.BJAM = bjam_exe.srcpath()
            return 0
        Logs.error('bjam bootsrap succeeded, but cannot find bjam executable.')
        return -1

class bjam_build(Task):
    ext_in = 'bjam_exe'
    ext_out = 'install'
    vars = ['BJAM_TOOLSET']
    def run(self):
        env = self.env
        gen = self.generator
        path = gen.path
        bld = gen.bld
        if hasattr(gen, 'root'):
            build_root = path.find_node(gen.root)
        else:
            build_root = path
        jam = bld.srcnode.find_resource(env.BJAM_CONFIG)
        if jam:
            Logs.debug('bjam: Using jam configuration from ' + jam.srcpath())
            jam_rel = jam.relpath_gen(build_root)
        else:
            Logs.warn('No build configuration in build_config/user-config.jam. Using default')
            jam_rel = None
        bjam_exe = bld.srcnode.find_node(env.BJAM)
        if not bjam_exe:
            Logs.error('env.BJAM is not set')
            return -1
        bjam_exe_rel = bjam_exe.path_from(build_root)
        cmd = ([bjam_exe_rel] +
            (['--user-config=' + jam_rel] if jam_rel else []) +
            ['--stagedir=' + path.get_bld().path_from(build_root)] +
            ['--debug-configuration'] +
            ['--with-' + lib for lib in self.generator.boost_libs] +
            (['toolset=' + env.BJAM_TOOLSET] if env.BJAM_TOOLSET else []) +
            ['link=' + 'shared'] +
            ['variant=' + 'release']
        )
        ret = self.exec_command(cmd, cwd=build_root.srcpath())
        if ret != 0:
            return ret
        self.set_outputs(path.get_bld().ant_glob('lib/*') + path.get_bld().ant_glob('bin/*'))
        return 0

class bjam_installer(Task):
    ext_in = 'install'
    def run(self):
        gen = self.generator
        path = gen.path
        for idir, pat in [('${LIBDIR}', 'lib/*'), ('${BINDIR}', 'bin/*')]:
            files = []
            for n in path.get_bld().ant_glob(pat):
                try:
                    from os import readlink
                    t = readlink(n.srcpath())
                    gen.bld.symlink_as(sep.join([idir, n.name]), t, postpone=False)
                except OSError, ImportError:
                    files.append(n)
            gen.bld.install_files(idir, files, postpone=False)
        return 0

