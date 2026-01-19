import os
import logging
import paramiko
import time
from datetime import datetime
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# --- CARREGAR CONFIGURAÇÕES ---
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
# O int() é necessário porque variáveis de ambiente vêm sempre como string
USUARIO_AUTORIZADO_ID = int(os.getenv("AUTH_USER_ID"))
USER_SSH_BASE = os.getenv("SSH_USER", "suporte")

# --- FUNÇÃO DA SENHA (Lógica pdv@ + dia + mes + hostId) ---
def gerar_senha_dinamica(host_index):
    now = datetime.now()
    dia_str = str(now.day).zfill(2)
    mes_str = str(now.month) # Jan = 1, Out = 10
    
    # Exemplo dia 03, mês 1: "031" + 20 = 51 -> pdv@51
    base_calculo = int(dia_str + mes_str)
    senha_final = base_calculo + host_index
    return f"pdv@{senha_final}"

# --- LÓGICA SSH ---
def execute_ssh_command(host_ip, host_index, command):
    try:
        senha = gerar_senha_dinamica(host_index)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        client.connect(
            hostname=host_ip, 
            username=USER_SSH_BASE, 
            password=senha, 
            timeout=8
        )
        
        # get_pty=True simula um terminal real, necessário para comandos sudo
        stdin, stdout, stderr = client.exec_command(command, get_pty=True)
        
        # Opcional: se o sudo pedir senha, poderíamos enviar aqui:
        # stdin.write(senha + '\n')
        # stdin.flush()

        output = stdout.read().decode()
        client.close()
        return output if output else "Comando enviado com sucesso."
    except Exception as e:
        return f"❌ Erro de conexão: {str(e)}"

# --- MIDDLEWARE DE SEGURANÇA ---
def is_authorized(update: Update):
    return update.effective_user.id == USUARIO_AUTORIZADO_ID

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("⛔ Acesso negado. Usuário não autorizado.")
        return

    keyboard = []
    for i in range(1, 35):
        label = f"Host {str(i).zfill(2)}"
        callback_data = f"host_{i}"
        if (i-1) % 4 == 0: keyboard.append([])
        keyboard[-1].append(InlineKeyboardButton(label, callback_data=callback_data))

    await update.message.reply_text(
        "🛠 **Painel de Manutenção**\nSelecione o host (172.23.153.101-134):",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_authorized(update):
        await query.answer("Não autorizado", show_alert=True)
        return

    await query.answer()
    
    if query.data.startswith("host_"):
        h_id = int(query.data.split("_")[1])
        ip = f"172.23.153.{100 + h_id}"
        context.user_data['host_ip'] = ip
        context.user_data['host_id'] = h_id
        
        keyboard = [
            [InlineKeyboardButton("🚀 Restart App", callback_data="run_app")],
            [InlineKeyboardButton("♻️ Reboot Machine", callback_data="run_reboot")],
            [InlineKeyboardButton("⬅️ Voltar", callback_data="back_to_list")]
        ]
        await query.edit_message_text(
            f"📍 **Host Selecionado:** {ip}\nUsuário: `{USER_SSH_BASE}`\nO que deseja fazer?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif query.data.startswith("run_"):
        ip = context.user_data.get('host_ip')
        h_id = context.user_data.get('host_id')
        cmd = "sudo restart-application.sh" if "app" in query.data else "sudo init 6"
        
        await query.edit_message_text(f"⏳ Processando `{cmd}` em `{ip}`...")
        res = execute_ssh_command(ip, h_id, cmd)
        await query.message.reply_text(f"🏁 **Resultado {ip}:**\n`{res}`", parse_mode="Markdown")

    elif query.data == "back_to_list":
        await start(update, context)

# --- INICIALIZAÇÃO ---
if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🚀 Bot iniciado com sucesso!")
    app.run_polling()

# ... (todo o seu código anterior aqui)
#auto-reinicialização do bot

if __name__ == "__main__":
    if not TOKEN or not LISTA_AUTORIZADA:
        print("❌ Erro: Verifique as variáveis no arquivo .env")
    else:
        while True:
            try:
                print(f"🚀 Bot iniciado! Usuários: {LISTA_AUTORIZADA}")
                app = Application.builder().token(TOKEN).build()
                app.add_handler(CommandHandler("start", start))
                app.add_handler(CallbackQueryHandler(button_handler))
                
                app.run_polling(poll_interval=1.0)
            except Exception as e:
                print(f"⚠️ Ocorreu um erro fatal: {e}")
                print("🔄 Reiniciando o bot em 5 segundos...")
                time.sleep(5)
