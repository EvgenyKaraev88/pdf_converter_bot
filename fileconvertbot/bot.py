import os
import tempfile
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

from converters.image_to_pdf import convert_image_to_pdf
from utils.file_validation import validate_file_type, validate_file_size
from utils.temp_manager import cleanup_temp_files

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define conversation states
START, WAITING_FILE, PROCESSING = range(3)

# Store user selections temporarily
user_selections = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send welcome message and conversion options."""
    user = update.effective_user
    
    keyboard = [
        [
            InlineKeyboardButton("📷 Image to PDF", callback_data='image_to_pdf')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        f'Привет {user.mention_html()}! 👋\n\n'
        f'Я FileConvertBot - ваш мгновенный конвертер форматов файлов.\n\n'
        f'<b>Выберите тип конверсии:</b>',
        reply_markup=reply_markup
    )
    
    return START

async def handle_conversion_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the user's conversion type selection."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    conversion_type = query.data
    
    # Store user selection
    user_selections[user_id] = conversion_type
    
    # Send appropriate prompt based on selection
    prompts = {
        'image_to_pdf': 'Пожалуйста, пришлите мне файл изображения (JPG/PNG) для конвертации в PDF.'
    }
    
    await query.edit_message_text(text=f"Выбрано: {prompts[conversion_type]}\n\nПожалуйста, отправьте файл сейчас.")
    
    return WAITING_FILE

async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle uploaded file and initiate conversion."""
    user_id = update.effective_user.id
    
    if user_id not in user_selections:
        await update.message.reply_text(
            "Please select a conversion type first using /start command."
        )
        return ConversationHandler.END
    
    conversion_type = user_selections[user_id]
    
    # Get file info
    file_obj = None
    
    # Check if the message contains a document
    if update.message.document:
        file_obj = update.message.document
        file_ext = os.path.splitext(file_obj.file_name)[1].lower()
    elif update.message.photo:
        # Handle photos - get the largest photo
        file_obj = sorted(update.message.photo, key=lambda x: x.width * x.height, reverse=True)[0]
        file_ext = '.jpg'  # Photos from Telegram are always JPEG
    else:
        await update.message.reply_text(
            "❌ Файл не найден. Пожалуйста, отправьте действительный файл."
        )
        return WAITING_FILE
    
    # Validate file type
    expected_extensions = {
        'image_to_pdf': ['.jpg', '.jpeg', '.png']
    }
    
    if file_ext not in expected_extensions[conversion_type]:
        await update.message.reply_text(
            f"❌ Неверный формат файла. Ожидаемый: {', '.join(expected_extensions[conversion_type])}\n"
            f"Полученный: {file_ext}\n\nПожалуйста, попробуйте еще раз, выбрав правильный тип файла."
        )
        return WAITING_FILE
    
    # Download the file
    try:
        new_file = await context.bot.get_file(file_obj.file_id)
        
        # Check file size (Telegram limit is 6MB)
        if hasattr(file_obj, 'file_size') and file_obj.file_size > 6 * 1024 * 1024:  # 6MB
            await update.message.reply_text(
                "❌ Размер файла превышает лимит 6 МБ. Пожалуйста, пришлите файл меньшего размера."
            )
            return WAITING_FILE
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_input:
            await new_file.download_to_memory(temp_input)
            input_path = temp_input.name
        
        # Process file based on conversion type
        try:
            await update.message.reply_text("🔄 Обработка вашего файла...")
            
            output_path = None
            
            if conversion_type == 'image_to_pdf':
                output_path = convert_image_to_pdf(input_path)
            
            if output_path and os.path.exists(output_path):
                # Send the converted file
                with open(output_path, 'rb') as output_file:
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=output_file,
                        caption="✅ Ваш файл конвертирован!"
                    )
                
                # Clean up temporary files
                cleanup_temp_files([input_path, output_path])
                
                # Clear user selection
                del user_selections[user_id]
                
                # Send restart keyboard directly
                keyboard = [[InlineKeyboardButton("🔄 Конвертировать другой файл", callback_data='start_over')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "Хотите конвертировать другой файл?",
                    reply_markup=reply_markup
                )
                
                # We're ending the conversation, but will handle restart separately
                return ConversationHandler.END
            else:
                await update.message.reply_text(
                    "❌ Преобразование не удалось. Пожалуйста, попробуйте еще раз с другим файлом."
                )
                cleanup_temp_files([input_path])
                return WAITING_FILE
                
        except Exception as e:
            logger.error(f"Conversion error: {str(e)}")
            await update.message.reply_text(
                f"❌ Преобразование не удалось: {str(e)}\nПожалуйста, попробуйте еще раз."
            )
            cleanup_temp_files([input_path])
            return WAITING_FILE
    
    except Exception as e:
        logger.error(f"File download error: {str(e)}")
        await update.message.reply_text(
            f"❌ Не удалось загрузить файл:{str(e)}"
        )
        return WAITING_FILE

async def start_over_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle restart callback - reinitialize the conversation."""
    query = update.callback_query
    await query.answer()
    
    # Clear any existing user selection
    user_id = query.from_user.id
    if user_id in user_selections:
        del user_selections[user_id]
    
    # Send the start message with keyboard
    keyboard = [
        [
            InlineKeyboardButton("📷 Image to PDF", callback_data='image_to_pdf')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=f'Привет {query.from_user.first_name}! 👋\n\n'
             f'Я FileConvertBot - ваш мгновенный конвертер форматов файлов.\n\n'
             f'<b>Выберите тип конверсии:</b>',
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    # Return START state to reactivate conversation
    return START

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel and end the conversation."""
    user = update.effective_user
    user_id = user.id
    
    # Clear user selection if exists
    if user_id in user_selections:
        del user_selections[user_id]
    
    await update.message.reply_text(
        "Операция отменена. Используйте /start, чтобы начать заново."
    )
    
    return ConversationHandler.END

def main() -> None:
    """Run the bot."""
    TOKEN = ""
    
    if not TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set.")
        return
    
    application = Application.builder().token(TOKEN).build()

    # Create conversation handler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(start_over_callback, pattern='^start_over$')
        ],
        states={
            START: [
                CallbackQueryHandler(handle_conversion_selection, pattern='^image_to_pdf$')
            ],
            WAITING_FILE: [
                MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file_upload),
                CommandHandler('cancel', cancel)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        conversation_timeout=300,
        name="file_converter",
        persistent=False,
    )

    application.add_handler(conv_handler)

    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
