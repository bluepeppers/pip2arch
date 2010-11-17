#!/usr/bin/python2
import sys
import xmlrpclib
import datetime
import logging
import argparse

BLANK_PKGBUILD = """
#Automatically generated by pip2arch on {date}

pkgname={pkg.outname}
pkgver={pkg.version}
pkgrel=1
pkgdesc="{pkg.description}"
url="{pkg.url}"
depends=('{pkg.pyversion}' {depends})
license=('{pkg.license}')
arch=('any')
source=('{pkg.download_url}')
md5sums=('{pkg.md5}')

build() {{
    cd $srcdir/{pkg.name}-{pkg.version}
    {pkg.pyversion} setup.py install --root="$pkgdir" || return 1
}}
"""

class pip2archException(Exception): pass
class VersionNotFound(pip2archException): pass
class LackOfInformation(pip2archException): pass

class Package(object):
    logging.info('Creating Server Proxy object')
    client = xmlrpclib.ServerProxy('http://pypi.python.org/pypi')
    depends = []
    
    def get_package(self, name, outname, version=None):
        if version is None:
            versions = self.client.package_releases(name)
            if len(versions) > 1:
                version = self.choose_version(versions)
            else:
                logging.info('Using version %s' % versions[0])
                version = versions[0]
        self.version = version
        
        self.outname = outname
        
        data = self.client.release_data(name, version)
        logging.info('Got release_data from PiPy')
        raw_urls = self.client.release_urls(name, version)
        logging.info('Got release_urls from PiPy')
        if not len(raw_urls) and len(data):
            raise LackOfInformation('PyPi did not return the neccisary information to create the PKGBUILD')
        elif len(data) and len(raw_urls):
            urls = {}
            for url in raw_urls:
                #if probabaly posix compat
                if url['filename'].endswith('.tar.gz'):
                    urls = url
            if not urls:
                raise pip2archException('Selected package version had no .tar.gz sources')
        elif not len(data):
            raise VersionNotFound('PyPi did not return any information for version {0}'.format(self.version))
        logging.info('Parsed release_urls data')
            
        
        pyversion = urls.get('python_version', '')
        if pyversion in ('source', 'any'):
            self.pyversion = 'python2'
        if pyversion.startswith('3'):
            self.pyversion = 'python'
        else:
            self.pyversion = 'python2'
            logging.info('Falling back to default python version')
        logging.info('Parsed python_version')
        
        try:
            self.name = data['name']
            self.description = data['summary']
            self.download_url = urls.get('url', '')
            self.md5 = urls['md5_digest']
            self.url = data.get('home_page', '')
            self.license = data['license']
        except KeyError:
            raise pip2archException('PiPy did not return needed information')
        logging.info('Parsed other data')
        
    def search(self, term):
        results = self.client.search({'description': str(term[1:])})
        for result in results:
            print ' - '.join((result['name'], result['summary']))
        #If no results
        if not results:
            print 'No results found'
    
    def choose_version(self, versions):
        print "Multiple versions found:"
        print ', '.join(versions)
        ver = raw_input('Which version would you like to use? ')
        if ver in versions:
            return ver
        else:
            print 'That was NOT one of the choices...'
            print 'Try again'
            self.choose_version(versions)
            
    def add_depends(self, depends):
        self.depends += depends
    
    def render(self):
        depends = '\'' + '\' \''.join(d for d in self.depends) + '\'' if self.depends else ''
        return BLANK_PKGBUILD.format(pkg=self, date=datetime.date.today(), depends=depends)


if __name__ == '__main__':
    
    
    parser = argparse.ArgumentParser(description='Convert a PiPy package into an Arch Linux PKGBUILD.')
    parser.add_argument('pkgname', metavar='N', action='store',
                        help='Name of PyPi package for pip2arch to process')
    parser.add_argument('-v', '--version', dest='version', action='store',
                        help='The version of the speciied PyPi package to process')
    parser.add_argument('-o', '--output', dest='outfile', action='store', type=argparse.FileType('w'),
                        default=open('PKGBUILD', 'w'),
                        help='The file to output the generated PKGBUILD to')
    parser.add_argument('-s', '--search', dest='search', action='store_true',
                        help="Search for given package name, instead of building PKGBUILD")
    parser.add_argument('-d', '--dependencies', dest='depends', action='append')
    parser.add_argument('-n', '--output-package-name', dest='outname', action='store', default=None,
                        help='The name of the package that pip2arch will generate')
    
    args = parser.parse_args()
    
    p = Package()
    
    if args.search:
        p.search(args.pkgname)
        sys.exit(0)
    
    try:
        p.get_package(name=args.pkgname, version=args.version, outname=args.outname or args.pkgname)
    except pip2archException as e:
        sys.exit('ERROR: {0}'.format(e))
    if args.depends:
        p.add_depends(args.depends)
    print "Got package information"
    args.outfile.write(p.render())
    print "Written PKGBUILD"