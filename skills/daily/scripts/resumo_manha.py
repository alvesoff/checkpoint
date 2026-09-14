#!/usr/bin/env python3
"""Ponte para `resumo.py manha`.

Existe porque `hermes cron --script` aceita um caminho e nenhum argumento, e o
resumo precisa saber se é manhã ou noite. Duas pontes de seis linhas custam
menos que duplicar a lógica em dois scripts que vão divergir.
"""
import os
import runpy
import sys

sys.argv = [sys.argv[0], "manha"]
runpy.run_path(os.path.join(os.path.dirname(os.path.realpath(__file__)), "resumo.py"),
               run_name="__main__")
