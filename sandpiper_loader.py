"""
	Copyright (C) 2021 The Sandpiper Authors. All rights reserved.

   	This document, part of the Sandpiper Framework software specification and package, is made available to you
   	under the terms of the Artistic License 2.0, which can be found at https://www.perlfoundation.org/artistic-license-20.html . For more information,
   	please feel free to visit us at https://www.sandpiperframework.org .

"""

import sqlite3
import openpyxl as opxl
import argparse
import time
import pathlib

args = argparse.ArgumentParser(description="Builds an SQLite Sandpiper database using the given SQL, and populates it using the given Excel file.")
args.add_argument("-i", "--initialize", metavar = "init_sql_file", default="", type=str, help="Initialize the database's structure using the given path to an SQL build file.")
args.add_argument("-e", "--excel", metavar="xlsx_file", default="", type=str, help="Path to an Excel file (.xlsx) with values to insert.")
args.add_argument("-db", "--db", metavar="db_file", type=str, default="", help="Optional database to use instead of creating one fresh. Warning: if -db/--db is used, this will potentially erase any pre-existing structures.")
pargs = args.parse_args()

# Should be using option groups but this will do for now
if pargs.initialize == "" and pargs.db == "":
	# We need at least one of these
	args.error("either -i/--initialize or -db/--db is required.")

# A simple class to hold fields, data, and a destination
class LightData:
	def __init__(self, destination = ""):
		self.fields = []
		self.data = []
		self.destination = destination

# Set up our data objects
plan = LightData("plans")
nodes = LightData("nodes")
controllers = LightData("controllers")
instances = LightData("instances")
instance_responders = LightData("instance_responders")
pools = LightData("pools")
slices = LightData("slices")
plan_slices = LightData("plan_slices")

node_unique_links = LightData("node_unique_links")
node_multi_links = LightData("node_multi_links")
node_multi_link_entries = LightData("node_multi_link_entries")

pool_unique_links = LightData("pool_unique_links")
pool_multi_links = LightData("pool_multi_links")
pool_multi_link_entries = LightData("pool_multi_link_entries")

slice_unique_links = LightData("slice_unique_links")
slice_multi_links = LightData("slice_multi_links")
slice_multi_link_entries = LightData("slice_multi_link_entries")

plan.fields = ["plan_uuid", "primary_node_uuid", "secondary_node_uuid", "status", "status_message", "local_description"];

nodes.fields = ["node_uuid", "node_description", "self_node", "created_on", "controller_uuid", "instance_uuid"]
controllers.fields = ["controller_uuid", "controller_description", "admin_contact", "admin_email", "created_on"]
instances.fields = ["instance_uuid", "software_description", "software_version", "capability_Level", "created_on"]
instance_responders.fields = ["instance_uuid", "capability_uri", "capability_role", "instance_responder_order"]
pools.fields = ["node_uuid", "pool_uuid", "pool_description", "pool_order", "created_on"]
slices.fields = ["pool_uuid", "slice_uuid", "slice_description", "slice_type", "file_name", "slice_order", "created_on"]
plan_slices.fields = ["plan_uuid", "slice_uuid", "plan_slice_order"]

node_unique_links.fields = ["node_uuid", "node_unique_link_uuid", "key_field", "key_value", "key_description", "link_order"]
node_multi_links.fields = ["node_uuid", "node_multi_link_uuid", "key_field", "link_order"]
node_multi_link_entries.fields = ["node_multi_link_uuid", "node_multi_linkEntry_uuid", "key_value", "key_description", "link_entry_order"]

pool_unique_links.fields = ["pool_uuid", "pool_unique_link_uuid", "key_field", "key_value", "key_description", "link_order"]
pool_multi_links.fields = ["pool_uuid", "pool_multi_link_uuid", "key_field", "link_order"]
pool_multi_link_entries.fields = ["pool_multi_link_uuid", "pool_multi_linkEntry_uuid", "key_value", "key_description", "link_entry_order"]

slice_unique_links.fields = ["slice_uuid", "slice_unique_link_uuid", "key_field", "key_value", "key_description", "link_order"]
slice_multi_links.fields = ["slice_uuid", "slice_multi_link_uuid", "key_field", "link_order"]
slice_multi_link_entries.fields = ["slice_multi_link_uuid", "slice_multi_link_entry_uuid", "key_value", "key_description", "link_entry_order"]

dbname = ""
if pargs.db == "":
	# Create the database we want
	dbname = f"Sandpiper_{time.strftime('%Y%m%dT%H%M%S')}.db"
	print(f"Creating new database {dbname}...")
else:
	dbname = pargs.db
	print(f"Using existing database {dbname}...")
db = sqlite3.connect(dbname)

if pargs.initialize != "":
	# Run the SQL file given, in this database
	print(f"Initializing database using {pargs.initialize}...")
	with pathlib.Path(pargs.initialize) as sf:
		db.executescript(sf.read_text())

if pargs.excel != "":
	#Load in data from the given Excel file
	print(f"Loading Excel file {pargs.excel}...")
	wb = opxl.load_workbook(pargs.excel) 

	planWs = wb.worksheets[0]
	nodeWs = wb.worksheets[1]
	dataWs = wb.worksheets[2]
	linkWs = wb.worksheets[3]

	# for each of the above worksheets, iterate through them and pull out the relevant data
	# (note that this needs to be in the same order as the fields listing of the data objects above)
	for ws in [planWs, nodeWs, dataWs, linkWs]:
		head = list(ws.values)[0]
		body = list(ws.values)[1:]

		if ws.title == "Plan":
			# Plan is simple enough
			for e in list(body):
				plan.data.append(list(e[0:3] + ("Approved", "", "Sample Plan")))

		if ws.title == "Nodes":
			# Nodes is one-row-per so no need to do fancy stuff here
			for e in list(body):
				nodes.data.append(list(e[0:5]) + list(e[9:10]))
				controllers.data.append(list(e[4:9]))
				instances.data.append(list(e[9:14]))
				# optional responders
				if e[14] is not None and e[14] != "":
					instance_responders.data.append(list(e[9:10]) + list(e[15:16]) + list(e[14:15]) + [1])
				if e[16] is not None and e[16] != "":
					instance_responders.data.append(list(e[9:10]) + list(e[17:18]) + list(e[16:17]) + [2])

		if ws.title == "Data":
			# Data can contain multiple pool entries; only use the first
			pool_i = 0
			slice_i = 0
			lastpool = ""
			for e in list(body):
				if e[1] != lastpool:
					lastpool = e[1]
					pool_i += 1
					slice_i = 0 # New pool, new order for slices
					pools.data.append(list(e[0:3]) + [pool_i] + list(e[3:4]))
				
				slice_i += 1
				slices.data.append(list(e[1:2]) + list(e[4:8]) + [slice_i] + list(e[8:9])) 

				plan_slices.data.append([plan.data[0][0]] + list(e[4:5]) + [slice_i])

		if ws.title == "Links":
			# Links can be either unique or multi. First column is the object type.
			linkorder = 0
			multilinkorder = 0
			linkentryorder = 0
			lastmulti = ""
			lastobj = ""
			for e in list(body):
				ulinks = None
				mlinks = None
				mlinkes = None

				if e[0] == "Node":
					ulinks = node_unique_links
					mlinks = node_multi_links
					mlinkes = node_multi_link_entries
				if e[0] == "Pool":
					ulinks = pool_unique_links
					mlinks = pool_multi_links
					mlinkes = pool_multi_link_entries
				if e[0] == "Slice":
					ulinks = slice_unique_links
					mlinks = slice_multi_links
					mlinkes = slice_multi_link_entries

				if lastobj != e[1]:
					linkorder = 0
					multilinkorder = 0
					lastobj = e[1]

				if e[3] is not None and e[3] != "": # Unique Link
					linkorder += 1
					ulinks.data.append(list(e[1:2]) + list(e[3:7]) + [linkorder])
				else: # Multi Link
					if lastmulti != e[7]:
						multilinkorder += 1
						linkentryorder = 0
						lastmulti = e[7]
						mlinks.data.append(list(e[1:2]) + list(e[7:9]) + [multilinkorder])
					mlinkes.data.append(list(e[7:8]) + list(e[9:12]) + [linkentryorder])

	sqlFile = pathlib.Path("test.sql")

	for d in [
			  controllers, instances, instance_responders, nodes, pools, slices
			, plan, plan_slices
			, node_unique_links, node_multi_links, node_multi_link_entries
			, pool_unique_links, pool_multi_links, pool_multi_link_entries
			, slice_unique_links, slice_multi_links, slice_multi_link_entries
		]:

		if len(d.data) > 0:
			sql = f"INSERT INTO {d.destination} ({', '.join(map(str, d.fields))}) VALUES ({', '.join('?' for f in d.fields)});"
			db.executemany(sql, d.data)

db.commit()
