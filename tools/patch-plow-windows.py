#!/usr/bin/env python3
"""Deixa a CLI `plow-agents` conseguir gravar o token no Windows.

A CLI grava a credencial com `os.fchmod(fd, 0o600)` e depois confere o modo do
arquivo. As duas coisas falham no Windows, e o Python decide qual:

  - `os.fchmod` nao existe la em toda versao (no 3.12 nao existe), e a chamada
    morre com AttributeError;
  - onde ela existe, `os.chmod` no Windows so alterna o atributo de somente
    leitura, o modo continua 0o666, e a checagem recusa a credencial com
    "refusing to install a credential that is not mode 600".

O resultado e o mesmo nos dois casos: a ativacao por iMessage e aceita, o token
volta, e a CLI morre na hora de salvar. Sem isto, instalar no Windows e
impossivel -- e o indice do hackathon mede instalacao concluida.

O arquivo continua protegido: ele fica sob o perfil do usuario, que a ACL do
NTFS restringe a esse usuario. No Unix nada muda, porque as duas correcoes sao
condicionais em tempo de execucao.

Roda toda vez, e nao so uma: o clone pode ser novo, e um `git pull` na CLI
desfaz a edicao. Aplicar duas vezes nao faz nada.
"""
import io
import sys

ALVO_FCHMOD = "        os.fchmod(descriptor, 0o600)\n"
NOVO_FCHMOD = (
    '        # os.fchmod nao existe no Windows em toda versao do Python.\n'
    '        if hasattr(os, "fchmod"):\n'
    "            os.fchmod(descriptor, 0o600)\n"
)

ALVO_MODO = "        if stat.S_IMODE(os.stat(temporary).st_mode) != 0o600:\n"
NOVO_MODO = (
    "        # Windows nao tem os bits de modo do POSIX: la o os.chmod so\n"
    "        # alterna o atributo de somente leitura, o modo fica 0o666 e esta\n"
    "        # checagem nunca passa. O arquivo continua protegido pela ACL do\n"
    "        # NTFS, por ficar sob o perfil do usuario. Checar um modo que a\n"
    "        # plataforma nao implementa so impede a gravacao.\n"
    '        if os.name != "nt" and '
    "stat.S_IMODE(os.stat(temporary).st_mode) != 0o600:\n"
)


def main(caminho):
    original = io.open(caminho, encoding="utf-8").read()
    texto = original
    feitos = []
    intactos = []

    for rotulo, alvo, novo, marca in (
        ("fchmod", ALVO_FCHMOD, NOVO_FCHMOD, 'hasattr(os, "fchmod")'),
        ("checagem de modo", ALVO_MODO, NOVO_MODO, 'os.name != "nt" and stat.S_IMODE'),
    ):
        if marca in texto:
            continue                      # ja aplicado
        if alvo in texto:
            texto = texto.replace(alvo, novo, 1)
            feitos.append(rotulo)
        else:
            intactos.append(rotulo)

    if texto != original:
        io.open(caminho, "w", encoding="utf-8", newline="\n").write(texto)

    if intactos:
        # Nao e erro: pode ser que a CLI tenha corrigido isto sozinha. Mas se o
        # login falhar no Windows depois desta linha, e aqui que se olha.
        print(
            "aviso: a CLI do Plow mudou onde este patch mexia (%s). "
            "Se o login falhar no Windows, comece por aqui." % ", ".join(intactos),
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("uso: patch-plow-windows.py <caminho do bin/plow-agents>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
