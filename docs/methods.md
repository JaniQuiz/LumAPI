# FDTD原生API的个人使用案例
## 目录
 - [自定义函数](#自定义函数)


## 自定义函数
我们可以在`python`中使用`eval`或者`feval`函数来自定义一些`FDTD`内部函数来方便我们使用。同时，经过测试，在创建大结构超表面时，使用内部的`FDTD`语言会比使用`python`来调用时创建结构快得多。因此建议我们编写一些函数来创建结构，使用`python`来控制创建结构和进行仿真的进程。

**注意：一定不要用python的for循环来构建大结构超表面，特别费时间**

下面是我曾经进行的一篇文章的仿真代码。参考文献：[Broadband achromatic polarization insensitive metalens  over 950 nm bandwidth in the visible and near-infrared](https://doi.org/10.3788/COL202220.013601)
```python
from LumAPI import *

# --------常量定义-------
um = 1e-6
nm = 1e-9

n = 50 # 50层圆环
wavelength = 450*nm
P = 450*nm
H = 1500*nm
base_thickness = 0.3*um
material_base = "Si3N4 - CNOP"
material_ring = "SiO2 - CNOP"

r_in = [45,45,45,45,45,45,45,50,50,50,55,55,55,60,60,65,65,70,70,60,60,65,70,75,75,65,70,70,75,65,70,60,65,55,60,45,35,40,25,15,20,25,30,15,20,30,15,30,15,35]
r_out = [200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,200,190,190,190,190,190,190,180,180,180,180,170,170,160,160,150,150,140,130,130,120,110,110,110,110,100,100,100,90,90,80,80]
r_in = np.array(r_in)
r_out = np.array(r_out)

# --------超透镜构建----------
fdtd = lumapi.FDTD()

fdtd.importmaterialdb("materials/"+material_base+".mdf") # 这里是我引入的额外的材料库
fdtd.importmaterialdb("materials/"+material_ring+".mdf")

cell_group = fdtd.addgroup(
    name="cell_group"
)
base = fdtd.addrect(
    name="base",
    x=0,
    y=0,
    x_span=2*(n+1)*P,
    y_span=2*(n+1)*P,
    z_min=-base_thickness,
    z_max=0,
    material=material_base
)

FDTD = fdtd.addfdtd(
    x=0,
    y=0,
    z=0,
    x_span=2*(n+1)*P,
    y_span=2*(n+1)*P,
    z_span=4*um,
)
FDTD.x_min_bc = 'PML'
FDTD.x_max_bc = 'PML'
FDTD.y_min_bc = 'PML'
FDTD.y_max_bc = 'PML'
FDTD.z_min_bc = 'PML'
FDTD.z_max_bc = 'PML' 

source = fdtd.addplane(
    name='source',
    x=0,
    y=0,
    z=-1*um,
    x_span=2*(n+1)*P,
    y_span=2*(n+1)*P,
    injection_axis='z-axis',
    direction='Forward',
    wavelength_start=targetwavelength,
    wavelength_stop=targetwavelength
)
# 添加光阑
aperture = fdtd.addrect(
    name='aperture',
    x=0,
    y=0,
    x_span=2*(n+1)*P,
    y_span=2*(n+1)*P,
    z_max=-0.3*um,
    z_min=-0.6*um,
    material='PEC(Perfect Electrical Conductor)'
)
etch = fdtd.addcircle(
    name='etch',
    x=0,
    y=0,
    z_min=-0.6*um,
    z_max=-0.3*um,
    radius=(n+1)*P,
    material='etch'
)

profile = fdtd.addpower(
    name='profile',
    monitor_type='2D Z-normal',
    x=0,
    y=0,
    z=1.5*um,
    x_span=2*(n+1)*P,
    y_span=2*(n+1)*P
)
# 设置监视器全局参数
fdtd.setglobalmonitor("sample spacing",'uniform')
fdtd.setglobalmonitor("use source limits",True)
# fdtd.setglobalmonitor("frequency points",50)

# 先进行一次保存，再创建主体结构
fdtd.save("metalens_CNOP.fsp")

scripts = '''
um = 1e-6;
nm = 1e-9;
function create_structure(P, H, r_in, r_out, n, material_ring){
    # 创建一系列圆环结构
    for(i=-n:n){
        for(j=-n:n){
            if((i^2+j^2<length(r_in)^2) and ((i!=0) or (j!=0))){
                r = round(sqrt(i^2+j^2));
                if(r>n){
                    r=n;
                }
                addring();
                set("name", "ring"+num2str(i)+"_"+num2str(j));
                set("x", i*P);
                set("y", j*P);
                set("z min", 0);
                set("z max", H);
                set("inner radius", r_in(r));
                set("outer radius", r_out(r));
                set("material", material_ring);
                addtogroup("cell_group");
            }
        }
    }
    
}
'''
fdtd.eval(scripts)
# fdtd.feval("create_structure.lsf") # 或者将scripts中的内容写入到lsf文件中，使用feval来执行

# 调用scripts中定义的函数
fdtd.create_structure(P, H, r_in, r_out, n, material_ring)

fdtd.save("metalens_CNOP.fsp")
# fdtd.run()  # 开始运行
fdtd.close() # 关闭程序
```





