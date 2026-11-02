@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
pushd "%~dp0"

rem ---------------------------------------------------------------------------
rem 课堂演示脚本：每段一个卖点，输出就是讲解要点。
rem   demo.cmd            交互菜单（默认，逐段 pause）
rem   demo.cmd a          从第 1 段连续跑到最后
rem   demo.cmd 3          只跑第 3 段，不停顿（适合彩排）
rem ---------------------------------------------------------------------------

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not exist "build\demo" mkdir "build\demo"

if not "%~1"=="" goto :from_arg

:menu
cls
echo ============================================================
echo   mycc 课堂演示  ^(C 子集 -^> 可配置 ISA 的 RISC-V 编译器^)
echo ============================================================
echo   1  环境自检 --doctor
echo   2  ISA 是变量：26 / 27 / 24 条
echo   3  默认 ISA：乘法走软件助手
echo   4  开启 mul：换成一条硬件乘法
echo   5  少一条指令的代价：--no-vshift
echo   6  一条命令出 Logisim ROM/RAM 镜像
echo   7  镜像预检：12 个程序 0 问题
echo   8  回归全绿：check.cmd
echo   9  打开 PySide6 工作台
echo   a  连续播放全部    q  退出
echo ============================================================
set "PICK="
set /p "PICK=请选择: "
if not defined PICK goto :menu
if /i "%PICK%"=="q" goto :end
if /i "%PICK%"=="a" goto :all
set "MODE=menu"
goto :dispatch

:from_arg
set "MODE=one"
set "PICK=%~1"
if /i "%PICK%"=="a" goto :all
goto :dispatch

:all
set "MODE=all"
goto :step1

:dispatch
if "%PICK%"=="1" goto :step1
if "%PICK%"=="2" goto :step2
if "%PICK%"=="3" goto :step3
if "%PICK%"=="4" goto :step4
if "%PICK%"=="5" goto :step5
if "%PICK%"=="6" goto :step6
if "%PICK%"=="7" goto :step7
if "%PICK%"=="8" goto :step8
if "%PICK%"=="9" goto :step9
echo.
echo 无效选择：%PICK%  （可用：1-9 / a / q）
if "%MODE%"=="one" goto :end
pause
goto :menu

rem ---------------------------------------------------------------------------
:step1
call :banner "1/9  环境自检（只需 Python，核心零第三方依赖）"
"%PY%" -m mycc --doctor
set "NEXT=:step2"
goto :after

:step2
call :banner "2/9  ISA 是变量：默认 26 条、开 mul 27 条、课堂 CPU 24 条"
echo [PF-01 默认]
"%PY%" -m mycc --dump-isa | findstr /b "profile: instructions:"
echo.
echo [PF-01 + mul]
"%PY%" -m mycc --dump-isa --enable mul | findstr /b "instructions:"
echo.
echo [logisim 课堂 CPU]
"%PY%" -m mycc --dump-isa --target logisim | findstr /b "profile: instructions:"
set "NEXT=:step3"
goto :after

:step3
call :banner "3/9  默认 ISA 下乘法是软件实现"
"%PY%" -m mycc examples/compiler/compiler_demo.c -o build\demo\default.s
"%PY%" -c "print('   汇编行数 =', sum(1 for _ in open('build/demo/default.s', encoding='utf-8')))"
echo   乘法调用点：
findstr /n /c:"__mulsi3" build\demo\default.s
set "NEXT=:step4"
goto :after

:step4
call :banner "4/9  加 --enable mul：一条硬件乘法（并解释为什么）"
"%PY%" -m mycc examples/compiler/compiler_demo.c --enable mul -o build\demo\mul.s --dump-lowering-report | findstr /c:"MUL"
"%PY%" -c "print('   汇编行数 =', sum(1 for _ in open('build/demo/mul.s', encoding='utf-8')))"
echo   硬件乘法指令：
findstr /n /c:"mul a0" build\demo\mul.s
set "NEXT=:step5"
goto :after

:step5
call :banner "5/9  硬件少一条指令，C 代码一行不改，代价可量化"
echo [默认：272 words]
"%PY%" -m mycc examples/compiler/shifts.c --target logisim -o build\demo\shifts.asm
echo.
echo [--no-vshift：281 words]
"%PY%" -m mycc examples/compiler/shifts.c --target logisim --no-vshift -o build\demo\shifts-nv.asm
echo.
echo   降级记录（节选）：
"%PY%" -m mycc examples/compiler/shifts.c --target logisim --no-vshift -o build\demo\shifts-nv.asm --dump-lowering-report | findstr /c:"SHL" /c:"SHR"
set "NEXT=:step6"
goto :after

:step6
call :banner "6/9  一条命令：汇编 + ROM + RAM 三件套"
"%PY%" -m mycc examples/logisim/knapsack.c --target logisim -o build\demo\knapsack.asm
echo   产物：
dir /b build\demo\knapsack.asm build\demo\knapsack.rom.hex build\demo\knapsack.ram.hex
set "NEXT=:step7"
goto :after

:step7
call :banner "7/9  写镜像前先自检：反汇编核对指令与容量"
"%PY%" -m tools.check_logisim
set "NEXT=:step8"
goto :after

:step8
call :banner "8/9  回归：全部自动化测试（约 20 秒）"
call check.cmd
echo   退出码 = %errorlevel%
set "NEXT=:step9"
goto :after

:step9
call :banner "9/9  PySide6 工作台（打开后按提示操作）"
echo   F5 编译 -^> 底部 Lowering 报告页 -^> 命令预览复制等价 CLI
start "mycc workbench" cmd /c launch.cmd
set "NEXT=:end"
goto :after

rem ---------------------------------------------------------------------------
:banner
echo.
echo ============================================================
echo   %~1
echo ============================================================
exit /b 0

:after
if "%MODE%"=="one" goto :end
echo.
pause
if "%MODE%"=="all" goto %NEXT%
goto :menu

:end
popd
endlocal
exit /b 0
