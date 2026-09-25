# Compactador de Pastas em ZIP
![image](https://github.com/FernandoAAB/Backup/blob/main/Doc/Diagram.png)


Duas partes que trabalham juntas, compartilhando o mesmo `config.json`:

| Arquivo | O que é | Quando roda |
|---|---|---|
| `zip_main.py` | Programa principal, com interface gráfica | Quando você abre manualmente |
| `background_zip.py` | Script de segundo plano, sem interface | 1x por dia, agendado pelo sistema |

Os dois **precisam ficar na mesma pasta**, porque compartilham o `config.json`
gerado pelo programa principal.

## Instalação

Com [uv](https://docs.astral.sh/uv/):
```bash
uv sync 
```

Ou com pip tradicional:
```bash
pip install -r requirements.txt
```

> `background_zip.py` não precisa dessa instalação — ele não usa
> interface gráfica, só bibliotecas padrão do Python.

## 1) Programa principal — `zip_main.py`

Interface para configurar e rodar o backup manualmente.

**Executar:**
```bash
uv run zip_main.py
```
ou, sem uv:
```bash
python zip_main.py
```

**O que faz:**
- Você adiciona uma ou mais **pastas de origem** e escolhe a **pasta de destino**.
- Ao clicar em **Iniciar Backup**, todas as pastas de origem são copiadas
  para dentro de **1 único arquivo `.zip`** no destino (não é 1 zip por pasta).
- O nome do zip leva a data e hora do backup no final —
  ex.: `PastaA_24-09-2026_16h50m.zip` (se só 1 origem) ou
  `Backup_24-09-2026_16h50m.zip` (se várias).
- Se o destino já tiver **5 ou mais `.zip`**, apaga todos menos o mais
  recente antes de criar o novo (fica sempre com no máximo 2 depois da limpeza).
- A tela mostra o **histórico de backups** já feitos no destino (nome, data/hora, tamanho).
- Botão no canto superior direito alterna entre tema **Escuro** e **Claro**.
- Suas escolhas (pastas, destino, tema) ficam salvas em `config.json` e
  recarregam sozinhas na próxima vez que você abrir o programa.

## 2) Script de segundo plano — `background_zip.py`

Faz o backup **automaticamente, sem abrir o programa principal**, de 5 em 5 dias.

**Como funciona:**
- Deve ser agendado para rodar **1x por dia**.
- Cada vez que roda, soma +1 num contador salvo em
  `backup_contador_dias.txt` (dia 1, dia 2, dia 3... até 5).
- Quando o contador chega a **5**:
  1. Lê as pastas de origem e o destino salvos no `config.json` pelo
     programa principal.
  2. Se o destino já tiver 5+ `.zip`, limpa mantendo só o mais recente.
  3. Cria o novo `.zip` combinando todas as pastas de origem.
  4. Reseta o contador para 1.
- Nos outros dias, só atualiza o contador e fecha — não mexe em nada.
- Tudo que acontece fica registrado em `backup_log.txt`, já que ninguém
  fica olhando a tela.

**Pré-requisito:** configure as pastas de origem e o destino pelo menos
uma vez no `zip_main.py` antes de agendar o daemon — ele só lê o
`config.json`, não tem como escolher pastas sozinho.

### Agendar no Windows (Agendador de Tarefas)

1. Abra o **Agendador de Tarefas** → **Criar Tarefa Básica**.
2. Disparador: **Diariamente**.
3. Ação: **Iniciar um programa**.
   - Programa/script: caminho do `python.exe` (ex.: `C:\Python312\python.exe`)
   - Argumentos: caminho completo do script, entre aspas —
     `"C:\caminho\para\background_zip.py"`

### Agendar no Linux/Mac (cron)

```bash
crontab -e
```
Adicione uma linha (roda todo dia às 9h, ajuste o horário como quiser):
```
0 9 * * * /usr/bin/python3 /caminho/para/background_zip.py
```

## Estrutura de arquivos

```
.
├── zip_main.py          # programa principal (GUI)
├── background_zip.py            # script de segundo plano
├── config.json                 # gerado pelo programa principal no primeiro uso
├── backup_contador_dias.txt    # gerado pelo daemon (contador de dias)
└── backup_log.txt              # gerado pelo daemon (histórico do que ele fez)
```
