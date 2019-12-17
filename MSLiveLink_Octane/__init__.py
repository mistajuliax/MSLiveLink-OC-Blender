# ##### QUIXEL AB - MEGASCANS LIVELINK FOR BLENDER #####
#
# The Megascans LiveLink plugin for Blender is an add-on that lets
# you instantly import assets with their shader setup with one click only.
#
# Because it relies on some of the latest 2.80 features, this plugin is currently
# only available for Blender 2.80 and forward.
#
# You are free to modify, add features or tweak this add-on as you see fit, and
# don't hesitate to send us some feedback if you've done something cool with it.
#
# ##### QUIXEL AB - MEGASCANS LIVELINK FOR BLENDER #####


# version: 0.5b 

import bpy, threading, os, time, json, socket

globals()['Megascans_DataSet'] = None

bl_info = {
    "name": "Megascans LiveLink Octane",
    "description": "Connects Octane Blender to Quixel Bridge for one-click imports with shader setup and geometry",
    "author": "Quixel",
    "version": (1, 2),
    "blender": (2, 81, 0),
    "location": "File > Import",
    "warning": "", # used for warning icon and text in addons panel
    "wiki_url": "https://docs.quixel.org/bridge/livelinks/blender/info_quickstart.html",
    "tracker_url": "https://docs.quixel.org/bridge/livelinks/blender/info_quickstart#release_notes",
    "support": "COMMUNITY",
    "category": "Import-Export"
}


# MS_Init_ImportProcess is the main asset import class.
# This class is invoked whenever a new asset is set from Bridge.

class MS_Init_ImportProcess():

    def __init__(self):
    # This initialization method create the data structure to process our assets
    # later on in the initImportProcess method. The method loops on all assets
    # that have been sent by Bridge.

        print("Initialized import class...")
        try:
            # Check if there's any incoming data
            if globals()['Megascans_DataSet'] != None:
                self.json_Array = json.loads(globals()['Megascans_DataSet'])

                # Start looping over each asset in the self.json_Array list
                for js in self.json_Array:

                    self.json_data = js

                    self.selectedObjects = []

                    self.assetType = self.json_data["type"]
                    self.assetPath = self.json_data["path"]
                    self.assetID = self.json_data["id"]
                    self.isMetal = bool(self.json_data["category"] == "Metal") 

                    baseTextures = ["albedo", "displacement", "normal", "roughness",
                                    "specular", "normalbump", "ao", "opacity",
                                    "translucency", "gloss", "metalness", "bump", "fuzz"]

                    # Create a list of tuples of all the textures maps available.
                    # This tuple is composed of (textureFormat, textureMapType, texturePath)
                    self.textureList = []
                    for obj in self.json_data["components"]:
                        if obj["type"] in baseTextures:
                            self.textureList.append( (obj["format"], obj["type"], obj["path"]) )

                    # Create a tuple list of all the 3d meshes  available.
                    # This tuple is composed of (meshFormat, meshPath)
                    self.geometryList = [(obj["format"], obj["path"]) for obj in self.json_data["meshList"]]

                    # Create name of our asset. Multiple conditions are set here
                    # in order to make sure the asset actually has a name and that the name
                    # is short enough for us to use it. We compose a name with the ID otherwise.
                    if "name" in self.json_data.keys():
                        self.assetName = self.json_data["name"].replace(" ", "_")
                    else:
                        self.assetName = os.path.basename(self.json_data["path"]).replace(" ", "_")
                    if len(self.assetName.split("_")) > 2:
                        self.assetName = "_".join(self.assetName.split("_")[:-1])

                    self.materialName = self.assetName + '_' + self.assetID

                    # Commented these lines, but you can use this to load the json data of a specific
                    # asset and retrieve information like tags, real-world size, scanning location, etc...
                    with open(os.path.join( self.assetPath, (self.assetID + ".json" ) ), 'r') as fl_:
                        assetJson =  json.load(fl_)

                    # Initialize the import method to start building our shader and import our geometry
                    self.initImportProcess()
                    print("Imported asset from " + self.assetName + " Quixel Bridge")

        except Exception as e:
            print( "Megascans LiveLink Error initializing the import process. Error: ", str(e) )


        globals()['Megascans_DataSet'] = None
    # this method is used to import the geometry and create the material setup.
    def initImportProcess(self):
        try:
            if len(self.textureList) >= 1:

                # Import geometry
                if len(self.geometryList) >= 1:
                    for obj in self.geometryList:
                        meshPath = obj[1]
                        meshFormat = obj[0]

                        if meshFormat.lower() == "fbx":
                            myOBJ = bpy.ops.import_scene.fbx(filepath=meshPath)
                            # get selected objects
                            obj_objects = [ o for o in bpy.context.scene.objects if o.select_get() ]
                            self.selectedObjects += obj_objects

                        elif meshFormat.lower() == "obj":
                            myOBJ = bpy.ops.import_scene.obj(filepath=meshPath)
                            # get selected objects
                            obj_objects = [ o for o in bpy.context.scene.objects if o.select_get() ]
                            self.selectedObjects += obj_objects

                # Create material
                mat = (bpy.data.materials.get( self.materialName ) or bpy.data.materials.new( self.materialName ))

                mat.use_nodes = True
                nodes = mat.node_tree.nodes

                # iterate through all objects
                for obj in self.selectedObjects:
                    # assign material to obj
                    obj.active_material = mat

                # Get a list of all available texture maps. item[1] returns the map type (albedo, normal, etc...).
                maps_ = [item[1] for item in self.textureList]
                parentName = "Principled BSDF"
                colorSpaces = ["sRGB", "Linear"]

                mat.node_tree.nodes[parentName].inputs[4].default_value = 1 if self.isMetal else 0 # Metallic value
                mat.node_tree.nodes[parentName].inputs[14].default_value = 1.52 # IOR Value

                y_exp = 310

                # Create the albedo setup.
                if "albedo" in maps_:

                    imgPath = [item[2] for item in self.textureList if item[1] == "albedo"]
                    if len(imgPath) >= 1:
                        imgPath = imgPath[0].replace("\\", "/")

                        texNode = nodes.new('ShaderNodeTexImage')
                        y_exp += -320
                        texNode.location = (-720, y_exp)
                        texNode.image = bpy.data.images.load(imgPath)
                        texNode.show_texture = True
                        texNode.image.colorspace_settings.name = colorSpaces[0]

                        mat.node_tree.links.new(nodes.get(parentName).inputs[0], texNode.outputs[0])

                # Create the roughness setup.
                if "roughness" in maps_:

                    imgPath = [item[2] for item in self.textureList if item[1] == "roughness"]
                    if len(imgPath) >= 1:
                        imgPath = imgPath[0].replace("\\", "/")

                        texNode = nodes.new('ShaderNodeTexImage')
                        y_exp += -320
                        texNode.location = (-720, y_exp)
                        texNode.image = bpy.data.images.load(imgPath)
                        texNode.show_texture = True
                        texNode.image.colorspace_settings.name = colorSpaces[1]

                        mat.node_tree.links.new(nodes.get(parentName).inputs[7], texNode.outputs[0])

                # Create the fuzziness setup.
                if "fuzz" in maps_:

                    imgPath = [item[2] for item in self.textureList if item[1] == "fuzz"]
                    if len(imgPath) >= 1:
                        imgPath = imgPath[0].replace("\\", "/")

                        texNode = nodes.new('ShaderNodeTexImage')
                        y_exp += -320
                        texNode.location = (-720, y_exp)
                        texNode.image = bpy.data.images.load(imgPath)
                        texNode.show_texture = True
                        texNode.image.colorspace_settings.name = colorSpaces[1]

                        mat.node_tree.links.new(nodes.get(parentName).inputs[10], texNode.outputs[0])
                        nodes.get(parentName).inputs[11].default_value = 1

                # Create the metalness setup
                if "metalness" in maps_:

                    imgPath = [item[2] for item in self.textureList if item[1] == "metalness"]
                    if len(imgPath) >= 1:
                        imgPath = imgPath[0].replace("\\", "/")

                        texNode = nodes.new('ShaderNodeTexImage')
                        y_exp += -320
                        texNode.location = (-720, y_exp)
                        texNode.image = bpy.data.images.load(imgPath)
                        texNode.show_texture = True
                        texNode.image.colorspace_settings.name = colorSpaces[1]

                        mat.node_tree.links.new(nodes.get(parentName).inputs[4], texNode.outputs[0])

                # Create the displacement setup.
                if "displacement" in maps_:

                    pass

                # Create the translucency setup.
                if "translucency" in maps_:

                    imgPath = [item[2] for item in self.textureList if item[1] == "translucency"]
                    if len(imgPath) >= 1:
                        imgPath = imgPath[0].replace("\\", "/")

                        texNode = nodes.new('ShaderNodeTexImage')
                        y_exp += -320
                        texNode.location = (-720, y_exp)
                        texNode.image = bpy.data.images.load(imgPath)
                        texNode.show_texture = True
                        texNode.image.colorspace_settings.name = colorSpaces[0]

                        mat.node_tree.links.new(nodes.get(parentName).inputs[3], texNode.outputs[0])

                # Create the opacity setup
                if "opacity" in maps_:

                    imgPath = [item[2] for item in self.textureList if item[1] == "opacity"]
                    if len(imgPath) >= 1:
                        imgPath = imgPath[0].replace("\\", "/")

                        texNode = nodes.new('ShaderNodeTexImage')
                        y_exp += -320
                        texNode.location = (256, 0)
                        texNode.image = bpy.data.images.load(imgPath)
                        texNode.show_texture = True
                        texNode.image.colorspace_settings.name = colorSpaces[1]

                        # mat.node_tree.links.new(nodes.get(parentName).inputs[4], texNode.outputs[0])

                        mixNode = nodes.new('ShaderNodeMixShader')
                        mixNode.location = (630, 0)
                        mixNode.inputs[0].default_value = 1
                        mat.node_tree.links.new(mixNode.inputs[0], texNode.outputs[0])

                        transpNode = nodes.new('ShaderNodeBsdfTransparent')
                        transpNode.location = (375, 168)
                        mat.node_tree.links.new(mixNode.inputs[1], transpNode.outputs[0])

                        mat.node_tree.links.new(nodes.get("Principled BSDF").outputs["BSDF"], mixNode.inputs[2])
                        mat.node_tree.links.new(nodes.get("Material Output").inputs["Surface"], mixNode.outputs[0])

                        mat.blend_method = 'CLIP'
                        mat.shadow_method = 'CLIP'

                # Create the normal map setup for Redshift.
                if "normal" in maps_:

                    normalNode = nodes.new('ShaderNodeNormalMap')
                    texNode = nodes.new('ShaderNodeTexImage')

                    imgPath = [item[2] for item in self.textureList if item[1] == "normal"]
                    if len(imgPath) >= 1:
                        imgPath = imgPath[0].replace("\\", "/")

                        texNode.location = (-720*1.5, y_exp)

                        texNode.image = bpy.data.images.load(imgPath)
                        texNode.show_texture = True
                        texNode.image.colorspace_settings.name = colorSpaces[1]

                        normalNode.location = (-450, y_exp)

                        mat.node_tree.links.new(nodes.get(parentName).inputs[19], normalNode.outputs[0])
                        texNode.image.colorspace_settings.name = colorSpaces[1]
                        mat.node_tree.links.new(texNode.outputs[0], normalNode.inputs[1])

                        mat.node_tree.links.new(texNode.outputs[0], normalNode.inputs[1])
        except Exception as e:
            print( "Megascans LiveLink Error while importing textures/geometry or setting up material. Error: ", str(e) )

class ms_Init(threading.Thread):
    
	#Initialize the thread and assign the method (i.e. importer) to be called when it receives JSON data.
    def __init__(self, importer):
        threading.Thread.__init__(self)
        self.importer = importer

	#Start the thread to start listing to the port.
    def run(self):
        try:
            run_livelink = True
            host, port = 'localhost', 28888
            #Making a socket object.
            socket_ = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            #Binding the socket to host and port number mentioned at the start.
            socket_.bind((host, port))

            #Run until the thread starts receiving data.
            while run_livelink:
                socket_.listen(5)
                #Accept connection request.
                client, addr = socket_.accept()
                data = ""
                buffer_size = 4096*2
                #Receive data from the client. 
                data = client.recv(buffer_size)
                if data == b'Bye Megascans':
                    run_livelink = False
                    break

                #If any data is received over the port.
                if data != "":
                    self.TotalData = b""
                    self.TotalData += data #Append the previously received data to the Total Data.
                    #Keep running until the connection is open and we are receiving data.
                    while run_livelink:
                        #Keep receiving data from client.
                        data = client.recv(4096*2)
                        if data == b'Bye Megascans':
                            run_livelink = False
                            break
                        #if we are getting data keep appending it to the Total data.
                        if data : self.TotalData += data
                        else:
                            #Once the data transmission is over call the importer method and send the collected TotalData.
                            self.importer(self.TotalData)
                            break
        except Exception as e:
            print( "Megascans LiveLink Error initializing the thread. Error: ", str(e) )

class thread_checker(threading.Thread):
    
	#Initialize the thread and assign the method (i.e. importer) to be called when it receives JSON data.
    def __init__(self):
        threading.Thread.__init__(self)

	#Start the thread to start listing to the port.
    def run(self):
        try:
            run_checker = True
            while run_checker:
                time.sleep(3)
                for i in threading.enumerate():
                    if(i.getName() == "MainThread" and i.is_alive() == False):
                        host, port = 'localhost', 28888
                        s = socket.socket()
                        s.connect((host,port))
                        data = "Bye Megascans"
                        s.send(data.encode())
                        s.close()
                        run_checker = False
                        break
        except Exception as e:
            print( "Megascans LiveLink Error initializing thread checker. Error: ", str(e) )
            pass

class MS_Init_LiveLink(bpy.types.Operator):

    bl_idname = "ms_livelink.py"
    bl_label = "Megascans LiveLink"
    socketCount = 0

    def execute(self, context):

        try:
            globals()['Megascans_DataSet'] = None
            self.thread_ = threading.Thread(target = self.socketMonitor)
            self.thread_.start()
            bpy.app.timers.register(self.newDataMonitor)
            return {'FINISHED'}
        except Exception as e:
            print( "Megascans LiveLink error starting blender plugin. Error: ", str(e) )
            return {"FAILED"}

    def newDataMonitor(self):
        try:
            if globals()['Megascans_DataSet'] != None:
                MS_Init_ImportProcess()
                globals()['Megascans_DataSet'] = None       
        except Exception as e:
            print( "Megascans LiveLink error starting blender plugin (newDataMonitor). Error: ", str(e) )
            return {"FAILED"}
        return 1.0


    def socketMonitor(self):
        try:
            #Making a thread object
            threadedServer = ms_Init(self.importer)
            #Start the newly created thread.
            threadedServer.start()
            #Making a thread object
            thread_checker_ = thread_checker()
            #Start the newly created thread.
            thread_checker_.start()
        except Exception as e:
            print( "Megascans LiveLink error starting blender plugin (socketMonitor). Error: ", str(e) )
            return {"FAILED"}

    def importer (self, recv_data):
        try:
            globals()['Megascans_DataSet'] = recv_data
        except Exception as e:
            print( "Megascans LiveLink error starting blender plugin (importer). Error: ", str(e) )
            return {"FAILED"}
        

def show_error_dialog(self, context):
     self.report({'INFO'}, "This is a test")

def menu_func_import(self, context):
    self.layout.operator(MS_Init_LiveLink.bl_idname, text="Megascans LiveLink")


def register():
    bpy.utils.register_class(MS_Init_LiveLink)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    # bpy.utils.unregister_class(MS_Init_LiveLink)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)



if __name__ == "__main__":
    register()
