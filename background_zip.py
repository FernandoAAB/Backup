"""
Script de segundo plano - Backup automático de 5 em 5 dias.
"""
import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

PASTA_SCRIPT = Path(__file__).resolve().parent
CONFIG_FILE = PASTA_SCRIPT / "config.json"                  # mesmo arquivo do programa principal
CONTADOR_FILE = PASTA_SCRIPT / "backup_contador_dias.txt"
LOG_FILE = PASTA_SCRIPT / "backup_log.txt"

LIMITE_DIAS = 5               # faz backup a cada 5 dias
LIMITE_ZIPS_PARA_LIMPEZA = 5  # se já tiver 5+ .zip no destino, limpa antes de criar um novo


def registrar_log(mensagem):
    linha = f"[{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] {mensagem}"
    print(linha)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except OSError:
        pass


def carregar_config():
    """Lê as pastas de origem e o destino salvos pelo programa principal."""
    if not CONFIG_FILE.exists():
        return [], ""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            dados = json.load(f)
        return dados.get("source_folders", []), dados.get("destination_folder", "")
    except (json.JSONDecodeError, OSError):
        return [], ""


def ler_contador():
    if not CONTADOR_FILE.exists():
        return 1
    conteudo = CONTADOR_FILE.read_text(encoding="utf-8").strip()
    return int(conteudo) if conteudo.isdigit() else 1


def salvar_contador(valor):
    CONTADOR_FILE.write_text(str(valor), encoding="utf-8")


def limpar_zips_antigos(destino_path):
    """Se já existem LIMITE_ZIPS_PARA_LIMPEZA ou mais .zip, apaga todos
    menos o mais recente, antes de criar o novo backup."""
    zips = sorted(destino_path.glob("*.zip"), key=lambda p: p.stat().st_mtime)
    if len(zips) >= LIMITE_ZIPS_PARA_LIMPEZA:
        for z in zips[:-1]:
            try:
                z.unlink()
                registrar_log(f"Removido backup antigo: {z.name}")
            except OSError as e:
                registrar_log(f"Erro ao remover {z.name}: {e}")


def montar_nome_zip(pastas):
    timestamp = datetime.now().strftime("%d-%m-%Y_%Hh%Mm")
    nome_base = Path(pastas[0]).name if len(pastas) == 1 else "Backup"
    return f"{nome_base}_{timestamp}"


def fazer_backup(pastas, destino):
    """Copia todas as pastas de origem para dentro de UM único .zip no destino.
    Retorna (sucesso: bool, caminho_zip: str|None)."""
    destino_path = Path(destino)
    destino_path.mkdir(parents=True, exist_ok=True)
    limpar_zips_antigos(destino_path)

    nomes_usados = set()
    alguma_copiada = False

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        for origem_str in pastas:
            origem = Path(origem_str)
            if not origem.exists() or not origem.is_dir():
                registrar_log(f"[FALHA] Pasta não encontrada: {origem_str}")
                continue

            nome_pasta = origem.name
            contador = 1
            while nome_pasta in nomes_usados:
                nome_pasta = f"{origem.name}_{contador}"
                contador += 1
            nomes_usados.add(nome_pasta)

            try:
                shutil.copytree(origem, tmp_path / nome_pasta)
                alguma_copiada = True
                registrar_log(f"[OK] Copiada: {origem_str}")
            except Exception as e:
                registrar_log(f"[FALHA] Erro ao copiar {origem_str}: {e}")

        if not alguma_copiada:
            return False, None

        nome_zip = montar_nome_zip(pastas)
        caminho_zip = destino_path / f"{nome_zip}.zip"
        base_name = str(destino_path / nome_zip)
        try:
            shutil.make_archive(base_name=base_name, format="zip", root_dir=str(tmp_path))
            return True, str(caminho_zip)
        except Exception as e:
            registrar_log(f"[FALHA] Erro ao compactar: {e}")
            return False, None


def executar():
    contador = ler_contador()

    if contador >= LIMITE_DIAS:
        registrar_log(f"Contador atingiu {contador}/{LIMITE_DIAS} — iniciando backup.")

        pastas, destino = carregar_config()
        if not pastas or not destino:
            registrar_log(
                "Config incompleta (defina as pastas de origem e o destino no "
                "programa principal antes de agendar este script). Backup não realizado."
            )
        else:
            sucesso, caminho_zip = fazer_backup(pastas, destino)
            if sucesso:
                registrar_log(f"Backup concluído: {caminho_zip}")
            else:
                registrar_log("Backup não pôde ser concluído (veja mensagens acima).")

        salvar_contador(1)
    else:
        novo_contador = contador + 1
        salvar_contador(novo_contador)
        registrar_log(f"Ainda não é dia de backup ({novo_contador}/{LIMITE_DIAS}). Nenhuma ação tomada.")


if __name__ == "__main__":
    executar()
