from ChemputerConvergence.libraries.Chempiler.chempiler.chempiler import Chempiler
import ChemputerConvergence.libraries.chemputerapi.ChemputerAPI as ChemputerAPI
import argparse
import os
import appdirs
from xdl.xdl import XDL


# python -m xdl.scripts.test


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--xdl_file', default='a.xdl',type=str)
    # parser.add_argument('--graph_file', default='undefined.json',type=str)
    parser.add_argument('--interactive', action='store_true')
    args = parser.parse_args()

    if not os.path.exists(args.xdl_file):
        raise FileNotFoundError(f"Can't find xdl file '{args.xdl_file}'.")

    # if not os.path.exists(args.graph_file):
    #     raise FileNotFoundError(f"Can't find graph file '{args.graph_file}'.")

    # 1.画图
    f = args.xdl_file
    x = XDL(args.xdl_file)
    graph_file = f[:-3] + 'json'
    x.graph(save=graph_file)

    # 2.编译
    x.prepare_for_execution(graph_file, interactive=args.interactive)


    # 3.执行
    platform_controller = Chempiler(
        experiment_code='test',
        output_dir=appdirs.user_data_dir('xdl'),
        graph_file=graph_file,
        simulation=True,
        device_modules=[ChemputerAPI]
    )


def main():
    parser = argparse.ArgumentParser(description="XDL流程分步执行工具（画图/编译/执行）")
    
    # 1. 公共参数（所有步骤都可能用到）
    parser.add_argument('--xdl_file', default='a.xdl', type=str, 
                        help="输入的XDL文件路径（默认：a.xdl）")
    parser.add_argument('--graph_file', default=None, type=str, 
                        help="生成/使用的Graph JSON文件路径（默认：与XDL同目录，后缀替换为.json）")
    parser.add_argument('--interactive', action='store_true', 
                        help="编译时启用交互模式（仅编译步骤生效）")
    
    # 2. 核心：步骤选择参数（必选，指定执行哪一步）
    parser.add_argument('--step', required=True, choices=['graph', 'compile', 'run'],
                        help="指定执行的步骤：\n"
                             "graph - 仅生成Graph图（第一步）\n"
                             "compile - 仅编译XDL流程（第二步，需先执行draw生成graph_file）\n"
                             "run - 仅执行编译后的流程（第三步，需先执行compile）")
    
    args = parser.parse_args()

    # --------------------------
    # 预处理：统一Graph文件路径（避免重复逻辑）
    # --------------------------
    if args.graph_file is None:
        # 默认：将XDL文件后缀改为.json（如 a.xdl → a.json）
        if args.xdl_file.endswith('.xdl'):
            args.graph_file = args.xdl_file[:-4] + '.json'
        else:
            # 若XDL文件无.xdl后缀，直接在末尾加.json
            args.graph_file = args.xdl_file + '.json'

    # --------------------------
    # 步骤1：仅生成Graph图（draw）
    # --------------------------
    if args.step == 'graph':
        # 检查XDL文件是否存在
        if not os.path.exists(args.xdl_file):
            raise FileNotFoundError(f"XDL文件不存在：{args.xdl_file}")
        
        # 加载XDL并生成Graph图
        print(f"[第一步：画图] 从 {args.xdl_file} 生成Graph图 → {args.graph_file}")
        x = XDL(args.xdl_file)
        x.graph(save=args.graph_file)  # 生成Graph JSON并保存
        print(f"[完成] Graph图已保存至：{os.path.abspath(args.graph_file)}")
        return  # 执行完第一步后退出，不继续后续步骤

    # --------------------------
    # 步骤2：仅编译XDL流程（compile）
    # --------------------------
    elif args.step == 'compile':
        # 检查依赖文件（XDL和Graph文件）
        if not os.path.exists(args.xdl_file):
            raise FileNotFoundError(f"XDL文件不存在：{args.xdl_file}")
        if not os.path.exists(args.graph_file):
            raise FileNotFoundError(
                f"Graph文件不存在！请先执行 'python 脚本名.py --step draw' 生成，"
                f"当前期望路径：{args.graph_file}"
            )
        
        # 加载XDL并执行编译
        print(f"[第二步：编译] 从 {args.xdl_file} 编译，使用Graph文件：{args.graph_file}")
        x = XDL(args.xdl_file)
        x.prepare_for_execution(
            graph_file=args.graph_file,
            interactive=args.interactive  # 交互模式（用户指定）
        )
        print(f"[完成] XDL流程编译成功（交互模式：{args.interactive}）")
        return  # 执行完第二步后退出

    # --------------------------
    # 步骤3：仅执行编译后的流程（run）
    # --------------------------
    elif args.step == 'run':
        # 检查依赖文件（仅需Graph文件，编译已确保流程有效性）
        if not os.path.exists(args.graph_file):
            raise FileNotFoundError(
                f"Graph文件不存在！请先执行 'python 脚本名.py --step draw' 和 "
                f"'python 脚本名.py --step compile' 生成，当前期望路径：{args.graph_file}"
            )
        
        # 初始化Chempiler并执行流程
        print(f"[第三步：执行] 使用Graph文件 {args.graph_file} 启动流程")
        platform_controller = Chempiler(
            experiment_code='test',
            output_dir=appdirs.user_data_dir('xdl'),
            graph_file=args.graph_file,
            simulation=True,  # 模拟模式（可根据需求调整）
            device_modules=[ChemputerAPI]
        )
        x = XDL(args.xdl_file)
        
        x.prepare_for_execution(
            graph_file=args.graph_file,
            interactive=args.interactive  # 交互模式（用户指定）
        )
        x.execute(platform_controller)  # 启动执行
        # （注：若Chempiler需要显式调用"执行"方法，需补充，如 platform_controller.run()）
        print(f"[完成] 流程执行启动（模拟模式：{platform_controller.simulation}）")
        return


if __name__ == "__main__":
    main()