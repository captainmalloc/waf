#!/usr/bin/env python
# encoding: utf-8
# Philipp Bender, 2012
# Matt Clarkson, 2012

import re
from waflib.Task import Task
from waflib.TaskGen import extension
from waflib import Errors

"""
A simple tool to integrate protocol buffers into your build system.

Example for C++:

    def configure(conf):
        conf.load('compiler_cxx cxx protoc')

    def build(bld):
        bld(
                features = 'cxx cxxprogram'
                source   = 'main.cpp file1.proto proto/file2.proto',
                includes = '. proto',
                target   = 'executable')

Example for Python:

    def configure(conf):
        conf.load('python protoc')

    def build(bld):
        bld(
                features = 'py'
                source   = 'main.py file1.proto proto/file2.proto',
                protoc_includes  = 'proto')

Example for both Python and C++ at same time:

    def configure(conf):
        conf.load('cxx python protoc')

    def build(bld):
        bld(
                features = 'cxx py'
                source   = 'file1.proto proto/file2.proto',
                protoc_includes  = 'proto')	# or includes


Notes when using this tool:

- protoc command line parsing is tricky.

  The generated files can be put in subfolders which depend on
  the order of the include paths.

  Try to be simple when creating task generators
  containing protoc stuff.

"""

class protoc(Task):
	run_str = '${PROTOC} ${PROTOC_FL:PROTOC_FLAGS} ${PROTOC_ST:INCPATHS} ${PROTOC_ST:PROTOC_INCPATHS} ${SRC[0].bldpath()}'
	color   = 'BLUE'
	ext_out = ['.h', 'pb.cc', '.py']
	def scan(self):
		"""
		Scan .proto dependencies
		"""
		node = self.inputs[0]

		nodes = []
		names = []
		seen = []
		search_nodes = []

		if not node:
			return (nodes, names)

		if 'cxx' in self.generator.features:
			search_nodes = self.generator.includes_nodes

		if 'py' in self.generator.features:
			for incpath in getattr(self.generator, 'protoc_includes', []):
				search_nodes.append(self.generator.bld.path.find_node(incpath))

		def parse_node(node):
			if node in seen:
				return
			seen.append(node)
			code = node.read().splitlines()
			for line in code:
				m = re.search(r'^import\s+"(.*)";.*(//)?.*', line)
				if m:
					dep = m.groups()[0]
					for incnode in search_nodes:
						found = incnode.find_resource(dep)
						if found:
							nodes.append(found)
							parse_node(found)
						else:
							names.append(dep)

		parse_node(node)
		return (nodes, names)

@extension('.proto')
def process_protoc(self, node):
	incdirs = []
	out_nodes = []
	protoc_flags = []

	if 'cxx' in self.features:
		cpp_node = node.change_ext('.pb.cc')
		hpp_node = node.change_ext('.pb.h')
		self.source.append(cpp_node)
		out_nodes.append(cpp_node)
		out_nodes.append(hpp_node)

		#self.env.PROTOC_FLAGS = '--cpp_out=%s' % node.parent.get_bld().abspath() # <- this does not work
		protoc_flags.append('--cpp_out=%s' % node.parent.get_bld().bldpath())

	if 'py' in self.features:
		py_node = node.change_ext('_pb2.py')
		self.source.append(py_node)
		out_nodes.append(py_node)

		protoc_flags.append('--python_out=%s' % node.parent.get_bld().bldpath())

	if out_nodes:
		self.create_task('protoc', node, out_nodes)
		if not self.env.PROTOC_FLAGS:
			self.env.PROTOC_FLAGS = protoc_flags
	else:
		raise Errors.WafError('Feature %s not supported by protoc extra' % self.features)


	if isinstance(self.env.PROTOC_FLAGS, str):	# Backwards compatibility as run_str format changed
		self.env.PROTOC_FLAGS = [ self.env.PROTOC_FLAGS ]

	# Instruct protoc where to search for .proto included files. For C++ standard include files dirs are used,
	# but this doesn't apply to Python / Java
	for incpath in getattr(self, 'protoc_includes', []):
		incdirs.append(self.bld.path.find_node(incpath).bldpath())
	self.env.PROTOC_INCPATHS = incdirs

	use = getattr(self, 'use', '')
	if not 'PROTOBUF' in use:
		self.use = self.to_list(use) + ['PROTOBUF']

def configure(conf):
	conf.check_cfg(package="protobuf", uselib_store="PROTOBUF", args=['--cflags', '--libs'])
	conf.find_program('protoc', var='PROTOC')
	conf.env.PROTOC_ST = '-I%s'
	conf.env.PROTOC_FL = '%s'
