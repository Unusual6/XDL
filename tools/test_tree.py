from lxml import etree
from xdl.xdl.readwrite.utils import read_file

xdl_file = "a.xdl"
xdl_str = read_file(xdl_file)

xdl_tree = etree.fromstring(xdl_str)

# 遍历到 Synthesis
synthesis = xdl_tree.find("Synthesis")

# 再找 Procedure
procedure = synthesis.find("Procedure")

Reagents = synthesis.find("Reagents")

Hardware = synthesis.find("Hardware")

# 遍历步骤
for step in procedure.findall("*"):
    print(step.tag, step.attrib)

# 遍历 Reagents
for reagent in Reagents.findall("Reagent"):
    print(reagent.tag, reagent.attrib)  

# 遍历 Hardware
for hardware in Hardware.findall("HardwareItem"):
    print(hardware.tag, hardware.attrib)