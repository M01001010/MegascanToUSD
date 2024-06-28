
import hou


class process():
    def __init__(self, obj):
        self.obj = obj
        self.lop_network = obj.createNode("lopnet", "Asset_Lop")
        self.cop_network = obj.createNode("cop2net", "Asset_Cop")
        self.shader = obj.node("Asset_Material").children()[0]
        self.geo_names = [x.name() for x in obj.children() if x.type().name() == "geo"]
        self.library = "E:/library/megascan/3d/"+obj.name()
        self.usd_output_path = self.library+"/usd/" + '`chs("filename")`'
        self.file_node = None
        self.rop_node = None
        self.run()


    def run(self):
        self.construct_cop_network()
        self.export_aces_textures()
        self.construct_lop_network()
        self.obj.layoutChildren()
        

    def construct_component_geometry(self, assetname):
        component_geometry_node = self.lop_network.createNode("componentgeometry", "component_geometry")
        parm_template = hou.StringParmTemplate(name="assetname", label="asset name", num_components=1)
        parm_group = component_geometry_node.parmTemplateGroup()
        parm_group.addParmTemplate(parm_template)
        component_geometry_node.setParmTemplateGroup(parm_group)
        component_geometry_node.parm("assetname").set(assetname)

        sop_context = component_geometry_node.node("sopnet/geo")
        geo_out = sop_context.node("default")
        proxy_out = sop_context.node("proxy")
        simproxy_out = sop_context.node("simproxy")
        object_merge = sop_context.createNode("object_merge", "object_merge")
        poly_reduce = sop_context.createNode("polyreduce", "polyreduce")
        
        geo_out.setInput(0, object_merge, 0)
        proxy_out.setInput(0, poly_reduce, 0)
        simproxy_out.setInput(0, poly_reduce, 0)
        poly_reduce.setInput(0, object_merge, 0)

        object_merge.parm("objpath1").set(self.obj.path() + '/`chsop("../../../assetname")`')
        poly_reduce.parm("percentage").set(4)
        sop_context.layoutChildren()

        return component_geometry_node
        


    def construct_lop_network(self):
        first_component_geometry_node = self.construct_component_geometry(self.geo_names[0])
        loop_component_geometry_node = self.construct_component_geometry("Var`@ITERATIONVALUE`_LOD0")
        foreach_begin = self.lop_network.createNode("begincontextoptionsblock", "foreach_begin")
        foreach_end = self.lop_network.createNode("foreach", "foreach_end")
        variant_node = self.lop_network.createNode("componentgeometryvariants", "componentgeometryvariants")
        material_library = self._construct_material()
        component_material_node = self.lop_network.createNode("componentmaterial", "component_material")
        component_output_node = self.lop_network.createNode("componentoutput", "component_output")
        set_variant = self.lop_network.createNode("setvariant", "setvariant")
        
        foreach_begin.setInput(0, first_component_geometry_node, 0)
        variant_node.setInput(0, foreach_begin, 0)
        variant_node.setInput(1, loop_component_geometry_node, 0)
        foreach_end.setInput(2, variant_node, 0)
        set_variant.setInput(0, foreach_end, 0)
        if len(self.geo_names) == 1:
            component_material_node.setInput(0, first_component_geometry_node, 0)
        else:
            component_material_node.setInput(0, set_variant, 0)
        component_material_node.setInput(1, material_library, 0)
        component_output_node.setInput(0, component_material_node, 0)

        first_component_geometry_node.parm("geovariantname").set("Var1")
        loop_component_geometry_node.parm("geovariantname").set("Var`@ITERATIONVALUE`")
        foreach_end.parm("iterations").set(len(self.geo_names)+1)
        foreach_end.parm("iterrange").set("range")
        foreach_end.parm("firstiteration").set(1)
        foreach_end.parm("lastiteration").set(len(self.geo_names))
        set_variant.parm("primpattern1").set("/ASSET")
        set_variant.parm("variantset1").set("geo")
        set_variant.parm("variantname1").set("Var1")
        component_output_node.parm("rootprim").set("/"+self.obj.name())
        component_output_node.parm("lopoutput").set(self.usd_output_path)
        material_library.parm("matpathprefix").set("/ASSET/mtl/")
        material_library.parm("matnode1").set("out_material")
        # component_material_node.parm("primpattern1").set("/ASSET/geo")

        self.lop_network.layoutChildren()


    def construct_cop_network(self):
        self.file_node = self.cop_network.createNode("file", "texture_file")
        vop_filter_node = self.construct_vop_network()
        self.rop_node = self.cop_network.createNode("rop_comp", "rop_comp")
        vop_filter_node.setInput(0, self.file_node, 0)
        self.rop_node.setInput(0, vop_filter_node, 0)
        self.rop_node.parm("trange").set(0)
        self.cop_network.layoutChildren()


    def export_aces_textures(self):
        channels = ["basecolor"]
        for channel in channels:
            texture_path = self._get_principled_texture_path(channel)
            if not texture_path:
                continue
            self.file_node.parm("filename1").set(texture_path)
            aces_path = self._texture_path_to_aces(texture_path)
            self.rop_node.parm("copoutput").set(aces_path)
            self.rop_node.parm("execute").pressButton()
            

    def _get_principled_texture_path(self, channel):
        return self.shader.parm(channel+"_texture").eval()


    def _texture_path_to_aces(self, texture_path):
        return self.library +"/surface/"+ texture_path.split("/")[-1]
    

    def _get_aces_texture_path(self, channel):
        return self._texture_path_to_aces(self._get_principled_texture_path(channel))


    def _construct_material(self):
        self.material_library = self.lop_network.createNode("materiallibrary", "material_library")
        albedo_path = self._get_aces_texture_path("basecolor")
        roughness_path = self._get_principled_texture_path("rough")
        specular_path = self._get_principled_texture_path("reflect")
        opacity_path = self._get_principled_texture_path("opaccolor")
        normal_path = self._get_principled_texture_path("baseNormal")
        displacement_path = self._get_principled_texture_path("dispTex")

        std_surface = self.material_library.createNode("mtlxstandard_surface", "mtlxstandard_surface")
        surface_material = self.material_library.createNode("mtlxsurfacematerial", "out_material")
        surface_material.setNamedInput("surfaceshader", std_surface, "out")

        if(albedo_path):
            albedo_image = self.material_library.createNode("mtlximage", "albedo_image")
            std_surface.setNamedInput("base_color", albedo_image, "out")
            albedo_image.parm("file").set(albedo_path)

        if roughness_path:
            roughness_image = self.material_library.createNode("mtlximage", "roughness_image")
            std_surface.setNamedInput("specular_roughness", roughness_image, "out")
            roughness_image.parm("file").set(roughness_path)
            roughness_image.parm("signature").set("default")
        
        if specular_path:
            specular_image = self.material_library.createNode("mtlximage", "specular_image")
            std_surface.setNamedInput("specular", specular_image, "out")
            specular_image.parm("file").set(specular_path)
            specular_image.parm("signature").set("default")

        if opacity_path:
            opacity_image = self.material_library.createNode("mtlximage", "opacity_image")
            std_surface.setNamedInput("opacity", opacity_image, "out")
            opacity_image.parm("file").set(opacity_path)
        
        if normal_path:
            normalmap = self.material_library.createNode("mtlxnormalmap", "mtlximage")
            normal_image = self.material_library.createNode("mtlximage", "normal_image")
            std_surface.setNamedInput("normal", normalmap, "out")
            normalmap.setNamedInput("in", normal_image, "out")
            normal_image.parm("file").set(normal_path)
            normal_image.parm("signature").set("vector3")

        if displacement_path:
            disp_node = self.material_library.createNode("mtlxdisplacement", "mtlxdisplacement")
            disp_remap = self.material_library.createNode("mtlxremap", "disp_remap")
            displacement_image = self.material_library.createNode("mtlximage", "displacement_image")
            disp_node.setNamedInput("displacement", disp_remap, "out")
            disp_remap.setNamedInput("in", displacement_image, "out")
            surface_material.setNamedInput("displacementshader", disp_node, "out")
            displacement_image.parm("file").set(displacement_path)
            disp_remap.parm("outlow").set(-.5)
            disp_remap.parm("outhigh").set(.5)
            disp_node.parm("scale").set(.1)

        self.material_library.layoutChildren()
        return self.material_library



    def construct_vop_network(self):
        vop_filter_node = self.cop_network.createNode("vopcop2filter", "vop_filter")
        global_node = vop_filter_node.node("global1")
        out_node = vop_filter_node.node("output1")
        float_to_vector_node = vop_filter_node.createNode("floattovec", "floattovec")
        ocio_node = vop_filter_node.createNode("ocio_transform", "ocio_transform")
        ocio_node.parm("fromspace").set("Utility - Linear - sRGB")
        ocio_node.parm("tospace").set("ACES - ACEScg")
        vector_to_float_node = vop_filter_node.createNode("vectofloat", "vectofloat")
        float_to_vector_node.setNamedInput("fval1", global_node, "R")
        float_to_vector_node.setNamedInput("fval2", global_node, "G")
        float_to_vector_node.setNamedInput("fval3", global_node, "B")
        ocio_node.setNamedInput("from", float_to_vector_node, "vec")
        vector_to_float_node.setNamedInput("vec", ocio_node, "to")
        out_node.setNamedInput("R", vector_to_float_node, "fval1")
        out_node.setNamedInput("G", vector_to_float_node, "fval2")
        out_node.setNamedInput("B", vector_to_float_node, "fval3")
        vop_filter_node.layoutChildren()
        return vop_filter_node

        



process(hou.selectedNodes()[0])



