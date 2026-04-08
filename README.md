# LumAPI：Lumerical Python接口的轻量级封装与增强库

本项目旨在简化 Lumerical FDTD 软件与 Python 环境的交互流程，提供自动化的路径配置工具，并封装了matlab数据文件.mat的读取和写入，以及常用的光学仿真后处理算法（如近场至远场变换）。

## 📖 核心功能
* **自动化环境配置**：自动识别系统中的 Lumerical 安装路径及版本，支持`Lumerical`安装和`Ansys`安装两种路径。
* **灵活集成**：支持将 API 库集成至特定 Python 解释器或独立项目目录。
* **便捷配置**：支持图形化界面和命令行界面两种配置方式。
* **API 增强**：支持原本接口，并对原本接口进行优化。
* **代码输入提示**：通过自定义pyi文件实现代码输入提示。
* **衍射积分函数**：封装了个人常用的衍射积分函数，且每个衍射积分函数结果均进行了验证。
* **数据保存读取**：封装了matlab数据文件.mat的读取和写入函数，方便与其他软件进行数据交互。
* **绘图函数增强**：封装了一些常用的matplotlib绘图功能，方便快速绘制合适的图像。


## 📦 如何安装 
[安装方式](install.md)

## 🗂️ 文档目录

### 使用指南

 - [使用文档](docs/usage.md)
 - [使用案例](docs/methods.md)

### 衍射积分函数验证

 - [基尔霍夫(Kirchhoff)标量衍射积分函数验证](docs/Kirchhoff.md)
 - [瑞利-索末菲(Rayleigh-Sommerfeld)标量衍射积分函数验证](docs/Rayleigh-Sommerfeld_Scalar.md)
 - [瑞利-索末菲(Rayleigh-Sommerfeld)矢量衍射积分函数验证](docs/Rayleigh-Sommerfeld_Vector.md)
 - [矢量角谱(Angular Spectrum)矢量衍射积分函数验证](docs/AngularSpectrum_Vector.md)

## 📜 许可证
本库遵循[GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.html)开源许可证

## 📧 联系作者
 - **作者**: [JaniQuiz](https://github.com/JaniQuiz)  
 - **邮箱**: janiquiz@163.com
 - **项目主页**: [LumAPI](https://github.com/JaniQuiz/LumAPI)
 - **问题反馈**: [GitHub Issues](https://github.com/JaniQuiz/LumAPI/issues)


<div align="center">
  Made with ❤️ by <a href="https://github.com/JaniQuiz">JaniQuiz</a>
  <br>
  如果这个项目对你有帮助，可以考虑给一个 ⭐️
</div>
