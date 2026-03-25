# Lumerical FDTD Python 自用脚本整理

本项目旨在简化 Lumerical FDTD 软件与 Python 环境的交互流程，提供自动化的路径配置工具，并封装了matlab数据文件.mat的读取和写入，以及常用的光学仿真后处理算法（如近场至远场变换）。

## 📖 核心功能
* **自动化环境配置**：自动识别系统中的 Lumerical 安装路径及版本。
* **灵活集成**：支持将 API 库集成至特定 Python 解释器或独立项目目录。
* **API 增强**：支持原本接口，并对原本接口参数进行优化。
* **衍射积分函数**：封装了个人常用的衍射积分函数，且每个衍射积分函数结果均进行了验证。
* **数据保存读取**：封装了matlab数据文件.mat的读取和写入函数，方便与其他软件进行数据交互。

---

## 📦 如何安装 
[安装方式](install.md)

---

## 📖 衍射积分函数验证文档
为确保我们的衍射积分函数的准确性，我们进行了验证，见[文档目录](docs/menu.md)

---

## 💻 使用指南

见[文档目录](docs/menu.md)

## 许可证
本库遵循[GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.html)开源许可证

## 联系作者
 - **作者**: [JaniQuiz](https://github.com/JaniQuiz)  
 - **邮箱**: janiquiz@163.com
 - **项目主页**: [LumAPI](https://github.com/JaniQuiz/LumAPI)
 - **问题反馈**: [GitHub Issues](https://github.com/JaniQuiz/LumAPI/issues)


<div align="center">
  Made with ❤️ by <a href="https://github.com/JaniQuiz">JaniQuiz</a>
  <br>
  如果这个项目对你有帮助，可以考虑给一个 ⭐️
</div>
