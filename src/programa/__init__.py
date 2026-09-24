
import json
import queue
import shutil
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

# Configuração (config.json)
CONFIG_FILE = Path(__file__).resolve().parent / "config.json"

# Quando já existem N ou mais .zip no destino, limpa antes de criar um novo.
LIMITE_ZIPS_PARA_LIMPEZA = 5

# Estado global do programa
pastas_origem = []
pasta_destino = ""
tema_atual = "Dark"

fila_progresso = queue.Queue()
compactando = False


def carregar_config():
    global pastas_origem, pasta_destino, tema_atual

    if not CONFIG_FILE.exists():
        return

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            dados = json.load(f)
        pastas_origem = dados.get("source_folders", [])
        pasta_destino = dados.get("destination_folder", "")
        tema_atual = dados.get("theme", "Dark")
    except (json.JSONDecodeError, OSError):
        pass


def salvar_config():
    dados = {
        "source_folders": pastas_origem,
        "destination_folder": pasta_destino,
        "theme": tema_atual,
    }
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=4, ensure_ascii=False)
    except OSError as e:
        print(f"Erro ao salvar configuração: {e}")



# Lógica de backup
def limpar_zips_antigos(destino_path):
    """Se já existem LIMITE_ZIPS_PARA_LIMPEZA ou mais .zip, apaga todos
    menos o mais recente, para não acumular backups sem limite."""
    zips = sorted(destino_path.glob("*.zip"), key=lambda p: p.stat().st_mtime)
    if len(zips) >= LIMITE_ZIPS_PARA_LIMPEZA:
        for z in zips[:-1]:
            try:
                z.unlink()
            except OSError:
                pass


def montar_nome_zip(pastas):
    """Nome do zip = nome da pasta de origem (se só uma) ou 'Backup' (se várias),
    seguido da data e hora do backup."""
    timestamp = datetime.now().strftime("%d-%m-%Y_%Hh%Mm")
    if len(pastas) == 1:
        nome_base = Path(pastas[0]).name
    else:
        nome_base = "Backup"
    return f"{nome_base}_{timestamp}"


def worker_backup(pastas, destino):
    """Roda em thread separada: copia todas as origens para uma pasta temporária
    e gera 1 único .zip no destino, avisando a interface via fila_progresso."""
    destino_path = Path(destino)
    destino_path.mkdir(parents=True, exist_ok=True)

    limpar_zips_antigos(destino_path)

    total = len(pastas)
    nomes_usados = set()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        alguma_copiada = False

        for i, origem_str in enumerate(pastas, start=1):
            origem = Path(origem_str)

            if not origem.exists() or not origem.is_dir():
                fila_progresso.put(("progresso", i, total, origem_str, False, "pasta não encontrada"))
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
                fila_progresso.put(("progresso", i, total, origem_str, True, "copiada"))
            except Exception as e:
                fila_progresso.put(("progresso", i, total, origem_str, False, f"erro ao copiar: {e}"))

        if not alguma_copiada:
            fila_progresso.put(("fim", False, None))
            return

        fila_progresso.put(("zipando",))

        nome_zip = montar_nome_zip(pastas)
        caminho_zip = destino_path / f"{nome_zip}.zip"
        base_name = str(destino_path / nome_zip)

        try:
            shutil.make_archive(base_name=base_name, format="zip", root_dir=str(tmp_path))
            fila_progresso.put(("fim", True, str(caminho_zip)))
        except Exception as e:
            fila_progresso.put(("fim", False, None, str(e)))



# Interface gráfica


def construir_janela():
    janela = ctk.CTk()
    janela.title("Compactador de Pastas em ZIP")
    janela.geometry("600x680")
    janela.minsize(600, 680)
    janela.grid_columnconfigure(0, weight=1)
    janela.grid_rowconfigure(2, weight=1)
    janela.grid_rowconfigure(3, weight=1)

    # --- Cabeçalho ---
    cabecalho = ctk.CTkFrame(janela, fg_color="transparent")
    cabecalho.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
    cabecalho.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        cabecalho, text="Compactador de Pastas", font=ctk.CTkFont(size=20, weight="bold")
    ).grid(row=0, column=0, sticky="w")

    botao_tema = ctk.CTkButton(cabecalho, text=texto_botao_tema(), width=110, command=alternar_tema)
    botao_tema.grid(row=0, column=1, sticky="e")

    # --- Pastas de origem ---
    origem_frame = ctk.CTkFrame(janela)
    origem_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
    origem_frame.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(origem_frame, text="Pastas de Origem (viram 1 único .zip)", font=ctk.CTkFont(weight="bold")).grid(
        row=0, column=0, sticky="w", padx=15, pady=(12, 0)
    )

    lista_origens = ctk.CTkScrollableFrame(origem_frame, height=120)
    lista_origens.grid(row=1, column=0, sticky="ew", padx=15, pady=10)
    lista_origens.grid_columnconfigure(0, weight=1)

    ctk.CTkButton(origem_frame, text="+ Adicionar Pasta", command=adicionar_pasta).grid(
        row=2, column=0, sticky="w", padx=15, pady=(0, 15)
    )

    # --- Destino + log ---
    corpo = ctk.CTkFrame(janela)
    corpo.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 10))
    corpo.grid_columnconfigure(0, weight=1)
    corpo.grid_rowconfigure(3, weight=1)

    ctk.CTkLabel(corpo, text="Pasta de Destino", font=ctk.CTkFont(weight="bold")).grid(
        row=0, column=0, sticky="w", padx=15, pady=(12, 0)
    )

    linha_destino = ctk.CTkFrame(corpo, fg_color="transparent")
    linha_destino.grid(row=1, column=0, sticky="ew", padx=15, pady=(5, 10))
    linha_destino.grid_columnconfigure(0, weight=1)

    campo_destino = ctk.CTkEntry(linha_destino, placeholder_text="Nenhuma pasta selecionada")
    campo_destino.grid(row=0, column=0, sticky="ew", padx=(0, 10))

    ctk.CTkButton(linha_destino, text="Selecionar...", width=110, command=selecionar_destino).grid(
        row=0, column=1
    )

    ctk.CTkLabel(corpo, text="Log", font=ctk.CTkFont(weight="bold")).grid(
        row=2, column=0, sticky="w", padx=15, pady=(5, 0)
    )

    caixa_log = ctk.CTkTextbox(corpo, state="disabled", wrap="word", height=100)
    caixa_log.grid(row=3, column=0, sticky="nsew", padx=15, pady=(5, 15))

    # --- Histórico de backups ---
    historico_frame = ctk.CTkFrame(janela)
    historico_frame.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 10))
    historico_frame.grid_columnconfigure(0, weight=1)
    historico_frame.grid_rowconfigure(1, weight=1)

    ctk.CTkLabel(historico_frame, text="Backups feitos", font=ctk.CTkFont(weight="bold")).grid(
        row=0, column=0, sticky="w", padx=15, pady=(12, 0)
    )

    lista_historico = ctk.CTkScrollableFrame(historico_frame)
    lista_historico.grid(row=1, column=0, sticky="nsew", padx=15, pady=(10, 15))
    lista_historico.grid_columnconfigure(0, weight=1)

    # --- Rodapé ---
    rodape = ctk.CTkFrame(janela, fg_color="transparent")
    rodape.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 20))
    rodape.grid_columnconfigure(0, weight=1)

    barra_progresso = ctk.CTkProgressBar(rodape)
    barra_progresso.set(0)
    barra_progresso.grid(row=0, column=0, sticky="ew", padx=(0, 10))

    botao_iniciar = ctk.CTkButton(rodape, text="Iniciar Backup", command=iniciar_backup)
    botao_iniciar.grid(row=0, column=1)

    widgets = {
        "janela": janela,
        "botao_tema": botao_tema,
        "lista_origens": lista_origens,
        "campo_destino": campo_destino,
        "caixa_log": caixa_log,
        "lista_historico": lista_historico,
        "barra_progresso": barra_progresso,
        "botao_iniciar": botao_iniciar,
    }
    return widgets


def texto_botao_tema():
    return "☀️ Claro" if tema_atual == "Dark" else "🌙 Escuro"


def atualizar_lista_origens():
    lista = widgets["lista_origens"]
    for w in lista.winfo_children():
        w.destroy()

    if not pastas_origem:
        ctk.CTkLabel(lista, text="Nenhuma pasta adicionada ainda.", text_color="gray").grid(
            row=0, column=0, sticky="w", padx=5, pady=5
        )
    else:
        for i, caminho in enumerate(pastas_origem):
            linha = ctk.CTkFrame(lista, fg_color="transparent")
            linha.grid(row=i, column=0, sticky="ew", pady=2)
            linha.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(linha, text=caminho, anchor="w").grid(row=0, column=0, sticky="ew", padx=5)
            ctk.CTkButton(
                linha, text="✕", width=28, fg_color="#B3261E", hover_color="#8C1D18",
                command=lambda c=caminho: remover_pasta(c),
            ).grid(row=0, column=1, padx=5)

    atualizar_estado_botao_iniciar()


def adicionar_pasta():
    pasta = filedialog.askdirectory(title="Selecione uma pasta de origem")
    if not pasta:
        return
    if pasta in pastas_origem:
        messagebox.showinfo("Aviso", "Essa pasta já está na lista.")
        return
    pastas_origem.append(pasta)
    salvar_config()
    atualizar_lista_origens()


def remover_pasta(caminho):
    if caminho in pastas_origem:
        pastas_origem.remove(caminho)
        salvar_config()
        atualizar_lista_origens()


def selecionar_destino():
    global pasta_destino
    pasta = filedialog.askdirectory(title="Selecione a pasta de destino")
    if not pasta:
        return
    pasta_destino = pasta
    widgets["campo_destino"].delete(0, "end")
    widgets["campo_destino"].insert(0, pasta_destino)
    salvar_config()
    atualizar_estado_botao_iniciar()
    atualizar_historico_backups()


def alternar_tema():
    global tema_atual
    tema_atual = "Light" if tema_atual == "Dark" else "Dark"
    ctk.set_appearance_mode(tema_atual)
    widgets["botao_tema"].configure(text=texto_botao_tema())
    salvar_config()


def log(mensagem):
    caixa = widgets["caixa_log"]
    caixa.configure(state="normal")
    caixa.insert("end", mensagem + "\n")
    caixa.see("end")
    caixa.configure(state="disabled")


def atualizar_estado_botao_iniciar():
    pode_iniciar = bool(pastas_origem) and bool(pasta_destino) and not compactando
    widgets["botao_iniciar"].configure(state="normal" if pode_iniciar else "disabled")


def atualizar_historico_backups():
    """Lê os .zip existentes na pasta de destino e mostra na tela, mais recente primeiro."""
    lista = widgets["lista_historico"]
    for w in lista.winfo_children():
        w.destroy()

    if not pasta_destino or not Path(pasta_destino).exists():
        ctk.CTkLabel(lista, text="Selecione uma pasta de destino para ver o histórico.", text_color="gray").grid(
            row=0, column=0, sticky="w", padx=5, pady=5
        )
        return

    zips = sorted(Path(pasta_destino).glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not zips:
        ctk.CTkLabel(lista, text="Nenhum backup feito ainda.", text_color="gray").grid(
            row=0, column=0, sticky="w", padx=5, pady=5
        )
        return

    for i, zip_path in enumerate(zips):
        stat = zip_path.stat()
        data_hora = datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M")
        tamanho_mb = stat.st_size / (1024 * 1024)

        linha = ctk.CTkFrame(lista, fg_color="transparent")
        linha.grid(row=i, column=0, sticky="ew", pady=2)
        linha.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(linha, text=zip_path.name, anchor="w").grid(row=0, column=0, sticky="ew", padx=5)
        ctk.CTkLabel(linha, text=f"{data_hora} · {tamanho_mb:.1f} MB", text_color="gray", anchor="e").grid(
            row=0, column=1, padx=5
        )


def iniciar_backup():
    global compactando
    if not pastas_origem or not pasta_destino:
        return

    compactando = True
    atualizar_estado_botao_iniciar()
    widgets["barra_progresso"].set(0)

    caixa = widgets["caixa_log"]
    caixa.configure(state="normal")
    caixa.delete("1.0", "end")
    caixa.configure(state="disabled")
    log(f"Iniciando backup de {len(pastas_origem)} pasta(s) em 1 único .zip...")

    thread = threading.Thread(
        target=worker_backup, args=(list(pastas_origem), pasta_destino), daemon=True
    )
    thread.start()
    widgets["janela"].after(100, verificar_fila_progresso)


def verificar_fila_progresso():
    global compactando
    try:
        while True:
            item = fila_progresso.get_nowait()

            if item[0] == "progresso":
                _, i, total, origem, sucesso, mensagem = item
                widgets["barra_progresso"].set(i / total * 0.8)  # 80% reservado para as cópias
                if sucesso:
                    log(f"[OK] Copiada: {origem}")
                else:
                    log(f"[FALHA] {origem} — {mensagem}")

            elif item[0] == "zipando":
                widgets["barra_progresso"].set(0.9)
                log("Compactando tudo em um único .zip...")

            elif item[0] == "fim":
                compactando = False
                sucesso = item[1]
                caminho_zip = item[2] if len(item) > 2 else None
                widgets["barra_progresso"].set(1 if sucesso else 0)

                if sucesso:
                    log(f"Backup concluído: {caminho_zip}")
                    messagebox.showinfo("Concluído", "Backup finalizado com sucesso.")
                else:
                    log("Nenhuma pasta pôde ser copiada. Backup não foi gerado.")
                    messagebox.showwarning("Falha", "Nenhuma pasta de origem pôde ser copiada.")

                atualizar_estado_botao_iniciar()
                atualizar_historico_backups()
                return
    except queue.Empty:
        pass

    if compactando:
        widgets["janela"].after(100, verificar_fila_progresso)



# Ponto de entrada
widgets = {}

if __name__ == "__main__":
    carregar_config()
    ctk.set_default_color_theme("blue")
    ctk.set_appearance_mode(tema_atual)

    widgets = construir_janela()
    atualizar_lista_origens()
    if pasta_destino:
        widgets["campo_destino"].insert(0, pasta_destino)
    atualizar_historico_backups()

    widgets["janela"].mainloop()
