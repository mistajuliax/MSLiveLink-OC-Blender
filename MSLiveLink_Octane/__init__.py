# [Quixel Megascans Livelink for Octane Blender Edition]
# 
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

import bpy, threading, os, time, json, socket
from bpy.types import Operator, AddonPreferences
from bpy.props import IntProperty, EnumProperty, BoolProperty

globals()['Megascans_DataSet'] = None

bl_info = {
    "name": "Megascans LiveLink Octane",
    "description": "Connects Octane Blender to Quixel Bridge for one-click imports with shader setup and geometry",
    "author": "Yichen Dou",
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

# Addon preferences
disp_types = [
    ('TEXTURE', 'Texture', 'Octane Texture Displacement'),
    ('VERTEX', 'Vertex', 'Octane Vertex Displacement')
]

disp_levels_texture = [
    ('OCTANE_DISPLACEMENT_LEVEL_256', '256', '256x256'),
    ('OCTANE_DISPLACEMENT_LEVEL_512', '512', '512x512'),
    ('OCTANE_DISPLACEMENT_LEVEL_1024', '1024', '1024x1024'),
    ('OCTANE_DISPLACEMENT_LEVEL_2048', '2048', '2048x2048'),
    ('OCTANE_DISPLACEMENT_LEVEL_4096', '4096', '4096x4096'),
    ('OCTANE_DISPLACEMENT_LEVEL_8192', '8192', '8192x8192')
]

class MSLiveLinkPrefs(AddonPreferences):
    bl_idname = __name__
    
    disp_type: EnumProperty(
        items=disp_types,
        name="Displacement Mode",
        description="Set default Octane displacement mode",
        default="TEXTURE"
    )

    disp_level_texture: EnumProperty(
        items=disp_levels_texture,
        name="Subdivision",
        default="OCTANE_DISPLACEMENT_LEVEL_4096"
    )

    disp_level_vertex: IntProperty(
        name="Subdivision",
        min=0,
        max=6,
        default=6
    )

    is_cavity_enabled: BoolProperty(
        name="Enable Cavity map",
        default=False
    )

    is_bump_enabled: BoolProperty(
        name="Enable Bump map",
        default=False
    )
    
    def draw(self, context):
        layout=self.layout
        col = layout.column()
        row = col.row()
        row.prop(self, "disp_type")
        if(self.disp_type=="TEXTURE"):
            row.prop(self, "disp_level_texture")
        else:
            row.prop(self, "disp_level_vertex")
        col.prop(self, "is_cavity_enabled")
        col.prop(self, "is_bump_enabled")


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

                baseTextures = ["albedo", "displacement", "normal", "roughness",
                                "specular", "normalbump", "ao", "opacity",
                                "translucency", "gloss", "metalness", "bump", "fuzz", "cavity"]

                # Start looping over each asset in the self.json_Array list
                for js in self.json_Array:

                    self.json_data = js

                    self.selectedObjects = []

                    self.assetType = self.json_data["type"]
                    self.assetPath = self.json_data["path"]
                    self.assetID = self.json_data["id"]
                    self.isMetal = self.json_data["category"] == "Metal" 

                    # Create a list of tuples of all the textures maps available.
                    # This tuple is composed of (textureFormat, textureMapType, texturePath)
                    self.textureList = [
                        (obj["format"], obj["type"], obj["path"])
                        for obj in self.json_data["components"]
                        if obj["type"] in baseTextures
                    ]

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

                    self.materialName = f'{self.assetName}_{self.assetID}'

                    # Commented these lines, but you can use this to load the json data of a specific
                    # asset and retrieve information like tags, real-world size, scanning location, etc...
                    with open(os.path.join(self.assetPath, f"{self.assetID}.json"), 'r') as fl_:
                        self.assetJson =  json.load(fl_)

                    # Initialize the import method to start building our shader and import our geometry
                    self.initImportProcess()
                    print(f"Imported asset from {self.assetName} Quixel Bridge")

        except Exception as e:
            print("Megascans LiveLink Error initializing the import process. Error: ", e)


        globals()['Megascans_DataSet'] = None
    # this method is used to import the geometry and create the material setup.
    def initImportProcess(self):
        try:
            if len(self.textureList) >= 1 and bpy.context.scene.render.engine == 'octane':

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
                mat = bpy.data.materials.new( self.materialName )
                mat.use_nodes = True
                nodes = mat.node_tree.nodes

                # replace default octane shader with a universal shader
                outNode = nodes[0]
                oldMainMat = nodes[1]
                mainMat = nodes.new('ShaderNodeOctUniversalMat')
                mainMat.location = oldMainMat.location
                nodes.remove(oldMainMat)
                mat.node_tree.links.new(outNode.inputs['Surface'], mainMat.outputs[0])

                # iterate through all objects
                for obj in self.selectedObjects:
                    # assign material to obj
                    obj.active_material = mat

                # Get a list of all available texture maps. item[1] returns the map type (albedo, normal, etc...).
                maps_ = [item[1] for item in self.textureList]
                colorSpaces = ["sRGB", "Linear"]

                mainMat.inputs['Metallic'].default_value = 1 if self.isMetal else 0 # Metallic value
                mainMat.inputs['Dielectric IOR'].default_value = 1.52 # IOR Value
                mainMat.inputs['Specular'].default_value = 0.5

                y_exp = 310

                prefs = bpy.context.preferences.addons[__name__].preferences

                # Create the albedo setup.
                if "albedo" in maps_:

                    imgPath = [item[2] for item in self.textureList if item[1] == "albedo"]
                    if len(imgPath) >= 1:
                        imgPath = imgPath[0].replace("\\", "/")

                        texNode = nodes.new('ShaderNodeOctImageTex')
                        y_exp += -320
                        texNode.location = (-720, y_exp)
                        texNode.image = bpy.data.images.load(imgPath)
                        texNode.show_texture = True
                        texNode.image.colorspace_settings.name = colorSpaces[0]

                        mat.node_tree.links.new(mainMat.inputs['Albedo color'], texNode.outputs[0])

                # Create the roughness setup.
                if "roughness" in maps_:

                    imgPath = [item[2] for item in self.textureList if item[1] == "roughness"]
                    if len(imgPath) >= 1:
                        imgPath = imgPath[0].replace("\\", "/")

                        texNode = nodes.new('ShaderNodeOctImageTex')
                        y_exp += -320
                        texNode.location = (-720, y_exp)
                        texNode.image = bpy.data.images.load(imgPath)
                        texNode.show_texture = True
                        texNode.image.colorspace_settings.name = colorSpaces[1]

                        mat.node_tree.links.new(mainMat.inputs['Roughness'], texNode.outputs[0])

                # Create the fuzziness setup.
                if "fuzz" in maps_:

                    imgPath = [item[2] for item in self.textureList if item[1] == "fuzz"]
                    if len(imgPath) >= 1:
                        imgPath = imgPath[0].replace("\\", "/")

                        texNode = nodes.new('ShaderNodeOctImageTex')
                        y_exp += -320
                        texNode.location = (-720, y_exp)
                        texNode.image = bpy.data.images.load(imgPath)
                        texNode.show_texture = True
                        texNode.image.colorspace_settings.name = colorSpaces[1]

                        mat.node_tree.links.new(mainMat.inputs['Sheen'], texNode.outputs[0])
                        mainMat.inputs['Sheen Roughness'].default_value = 0

                # Create the metalness setup
                if "metalness" in maps_:

                    imgPath = [item[2] for item in self.textureList if item[1] == "metalness"]
                    if len(imgPath) >= 1:
                        imgPath = imgPath[0].replace("\\", "/")

                        texNode = nodes.new('ShaderNodeOctImageTex')
                        y_exp += -320
                        texNode.location = (-720, y_exp)
                        texNode.image = bpy.data.images.load(imgPath)
                        texNode.show_texture = True
                        texNode.image.colorspace_settings.name = colorSpaces[1]

                        mat.node_tree.links.new(mainMat.inputs['Metallic'], texNode.outputs[0])

                # Create the displacement setup.
                if "displacement" in maps_:
                    
                    imgPath = [item[2] for item in self.textureList if item[1] == "displacement"]
                    if len(imgPath) >= 1:
                        imgPath = imgPath[0].replace("\\", "/")
                        texNode = nodes.new('ShaderNodeOctImageTex')
                        y_exp += -320
                        texNode.location = (-720, y_exp)
                        texNode.image = bpy.data.images.load(imgPath)
                        texNode.show_texture = True
                        texNode.image.colorspace_settings.name = colorSpaces[1]
                        if prefs.disp_type == "VERTEX":
                            texNode.border_mode = 'OCT_BORDER_MODE_CLAMP'

                        if prefs.disp_type == "TEXTURE":
                            dispNode = nodes.new('ShaderNodeOctDisplacementTex')
                            dispNode.displacement_level = prefs.disp_level_texture
                            #dispNode.displacement_filter = 'OCTANE_FILTER_TYPE_BOX'
                            dispNode.inputs['Mid level'].default_value = 0.5
                            dispNode.inputs['Height'].default_value = 0.1
                        else:
                            dispNode = nodes.new('ShaderNodeOctVertexDisplacementTex')
                            dispNode.inputs['Auto bump map'].default_value = True
                            dispNode.inputs['Mid level'].default_value = 0.1
                            dispNode.inputs['Height'].default_value = 0.1
                            dispNode.inputs['Subdivision level'].default_value = prefs.disp_level_vertex

                        dispNode.location = (-360, -680)

                        mat.node_tree.links.new(dispNode.inputs['Texture'], texNode.outputs[0])
                        mat.node_tree.links.new(mainMat.inputs['Displacement'], dispNode.outputs[0])

                # Create the translucency setup.
                if "translucency" in maps_:

                    imgPath = [item[2] for item in self.textureList if item[1] == "translucency"]
                    if len(imgPath) >= 1:
                        imgPath = imgPath[0].replace("\\", "/")

                        texNode = nodes.new('ShaderNodeOctImageTex')
                        y_exp += -320
                        texNode.location = (-720, y_exp)
                        texNode.image = bpy.data.images.load(imgPath)
                        texNode.show_texture = True
                        texNode.image.colorspace_settings.name = colorSpaces[0]

                        scatterNode = nodes.new('ShaderNodeOctScatteringMedium')
                        scatterNode.inputs['Absorption Tex'].default_value = (1, 1, 1, 1)
                        scatterNode.inputs['Invert abs.'].default_value = False
                        scatterNode.location = (-360, -1000)

                        mat.node_tree.links.new(mainMat.inputs['Transmission'], texNode.outputs[0])
                        mat.node_tree.links.new(mainMat.inputs['Medium'], scatterNode.outputs[0])

                    pass

                # Create the opacity setup
                if "opacity" in maps_:

                    imgPath = [item[2] for item in self.textureList if item[1] == "opacity"]
                    if len(imgPath) >= 1:
                        imgPath = imgPath[0].replace("\\", "/")

                        texNode = nodes.new('ShaderNodeOctImageTex')
                        # y_exp += -320
                        texNode.location = (256, 0)
                        texNode.image = bpy.data.images.load(imgPath)
                        texNode.show_texture = True
                        texNode.image.colorspace_settings.name = colorSpaces[1]

                        mixNode = nodes.new('ShaderNodeOctMixMat')
                        mixNode.location = (630, 0)
                        mixNode.inputs['Amount'].default_value = 1
                        mat.node_tree.links.new(mixNode.inputs['Amount'], texNode.outputs[0])

                        transpNode = nodes.new('ShaderNodeOctDiffuseMat')
                        transpNode.location = (256, -320)
                        transpNode.inputs['Opacity'].default_value = 0

                        mat.node_tree.links.new(mixNode.inputs['Material1'], mainMat.outputs[0])
                        mat.node_tree.links.new(mixNode.inputs['Material2'], transpNode.outputs[0])

                        mat.node_tree.links.new(outNode.inputs['Surface'], mixNode.outputs[0])

                        mat.blend_method = 'CLIP'
                        mat.shadow_method = 'CLIP'

                # Create the normal map setup for Redshift.
                if "normal" in maps_:
                    
                    texNode = nodes.new('ShaderNodeOctImageTex')

                    imgPath = [item[2] for item in self.textureList if item[1] == "normal"]
                    if len(imgPath) >= 1:
                        imgPath = imgPath[0].replace("\\", "/")

                        y_exp += -320
                        texNode.location = (-720, y_exp)

                        texNode.image = bpy.data.images.load(imgPath)
                        texNode.show_texture = True
                        texNode.image.colorspace_settings.name = colorSpaces[1]

                        texNode.image.colorspace_settings.name = colorSpaces[1]
                        mat.node_tree.links.new(mainMat.inputs['Normal'], texNode.outputs[0])

                # Create the specular map setup
                if "specular" in maps_:
                    texNode = nodes.new('ShaderNodeOctImageTex')

                    imgPath = [item[2] for item in self.textureList if item[1] == "specular"]
                    if len(imgPath) >= 1:
                        imgPath = imgPath[0].replace("\\", "/")

                        y_exp += -320
                        texNode.location = (-720, y_exp)

                        texNode.image = bpy.data.images.load(imgPath)
                        texNode.show_texture = True
                        texNode.image.colorspace_settings.name = colorSpaces[0]

                        mat.node_tree.links.new(mainMat.inputs['Specular'], texNode.outputs[0])
                else:
                    try:
                        rgbNode = nodes.new('ShaderNodeOctRGBSpectrumTex')
                        targetJson = self.assetJson["maps"] if ("maps" in self.assetJson) else self.assetJson["components"]
                        specularItems = [item for item in targetJson if item["type"] == "specular"]
                        if len(specularItems) > 0:
                            hexValue = specularItems[0]['averageColor'].lstrip('#')
                            specValue = [col/255 for col in [int(hexValue[i:i+2], 16) for i in (0, 2, 4)]]
                            specValue.append(1)

                            rgbNode.location = (-720, 200)
                            rgbNode.inputs[0].default_value = tuple(specValue)

                            mat.node_tree.links.new(mainMat.inputs['Specular'], rgbNode.outputs[0])
                    except Exception as e:
                        print( "Cannot find specular information : ", str(e) )

                # Create the bump map setup
                if ("bump" in maps_) and (prefs.is_cavity_enabled):
                    texNode = nodes.new('ShaderNodeOctImageTex')

                    imgPath = [item[2] for item in self.textureList if item[1] == "bump"]
                    if len(imgPath) >= 1:
                        imgPath = imgPath[0].replace("\\", "/")

                        y_exp += -320
                        texNode.location = (-720, y_exp)

                        texNode.image = bpy.data.images.load(imgPath)
                        texNode.show_texture = True
                        texNode.image.colorspace_settings.name = colorSpaces[1]

                        #mat.node_tree.links.new(mainMat.inputs['Bump'], texNode.outputs[0])

                if ("cavity" in maps_) and (prefs.is_cavity_enabled):
                    texNode = nodes.new('ShaderNodeOctImageTex')

                    imgPath = [item[2] for item in self.textureList if item[1] == "cavity"]
                    if len(imgPath) >= 1:
                        imgPath = imgPath[0].replace("\\", "/")

                        y_exp += -320
                        texNode.location = (-720, y_exp)

                        texNode.image = bpy.data.images.load(imgPath)
                        texNode.show_texture = True
                        texNode.image.colorspace_settings.name = colorSpaces[1]

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
    bl_label = "Megascans LiveLink Octane"
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
    self.layout.operator(MS_Init_LiveLink.bl_idname, text="Megascans LiveLink Octane")


def register():
    bpy.utils.register_class(MS_Init_LiveLink)
    bpy.utils.register_class(MSLiveLinkPrefs)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(MSLiveLinkPrefs)
    bpy.utils.unregister_class(MS_Init_LiveLink)



if __name__ == "__main__":
    register()
