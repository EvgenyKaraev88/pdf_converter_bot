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
from converters.word_to_pdf import convert_word_to_pdf
from converters.pdf_to_word import convert_pdf_to_word
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

# Store user selections temporarily (in production, consider using a database)
user_selections = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send welcome message and conversion options."""
    user = update.effective_user
    
    keyboard = [
        [
            InlineKeyboardButton("📷 Image to PDF", callback_data='image_to_pdf'),
            InlineKeyboardButton("📄 Word to PDF", callback_data='word_to_pdf')
        ],
        [
            InlineKeyboardButton("📋 PDF to Word", callback_data='pdf_to_word')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        f'Hi {user.mention_html()}! 👋\n\n'
        f'I\'m FileConvertBot - your instant file format converter.\n\n'
        f'<b>Choose a conversion type:</b>',
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
        'image_to_pdf': 'Please send me an image file (JPG/PNG) to convert to PDF.',
        'word_to_pdf': 'Please send me a Word document (.docx) to convert to PDF.',
        'pdf_to_word': 'Please send me a PDF file to convert to Word (.docx).'
    }
    
    await query.edit_message_text(text=f"Selected: {prompts[conversion_type]}\n\nUploading...")
    
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
    file_info = None
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
            "❌ No file found. Please send a valid file."
        )
        return WAITING_FILE
    
    # Validate file type
    expected_extensions = {
        'image_to_pdf': ['.jpg', '.jpeg', '.png'],
        'word_to_pdf': ['.docx'],
        'pdf_to_word': ['.pdf']
    }
    
    if file_ext not in expected_extensions[conversion_type]:
        await update.message.reply_text(
            f"❌ Invalid file format. Expected: {', '.join(expected_extensions[conversion_type])}\n"
            f"Received: {file_ext}\n\nPlease try again with the correct file type."
        )
        return WAITING_FILE
    
    # Download the file
    try:
        new_file = await context.bot.get_file(file_obj.file_id)
        
        # Check file size (Telegram limit is 20MB)
        if hasattr(file_obj, 'file_size') and file_obj.file_size > 20 * 1024 * 1024:  # 20MB
            await update.message.reply_text(
                "❌ File size exceeds 20MB limit. Please send a smaller file."
            )
            return WAITING_FILE
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_input:
            await new_file.download_to_memory(temp_input)
            input_path = temp_input.name
        
        # Process file based on conversion type
        try:
            await update.message.reply_text("🔄 Processing your file...")
            
            output_path = None
            
            if conversion_type == 'image_to_pdf':
                output_path = convert_image_to_pdf(input_path)
            elif conversion_type == 'word_to_pdf':
                output_path = convert_word_to_pdf(input_path)
            elif conversion_type == 'pdf_to_word':
                output_path = convert_pdf_to_word(input_path)
            
            if output_path and os.path.exists(output_path):
                # Send the converted file
                with open(output_path, 'rb') as output_file:
                    if conversion_type.endswith('_pdf'):
                        await context.bot.send_document(
                            chat_id=update.effective_chat.id,
                            document=output_file,
                            caption="✅ Your file has been converted! Download link above."
                        )
                    else:  # pdf_to_word
                        await context.bot.send_document(
                            chat_id=update.effective_chat.id,
                            document=output_file,
                            caption="✅ Your file has been converted! Download link above."
                        )
                
                # Clean up temporary files
                cleanup_temp_files([input_path, output_path])
                
                # Clear user selection
                del user_selections[user_id]
                
                # Offer to start again - but we need to handle this differently
                # Since we're outside the conversation handler at this point,
                # we just send the message with the restart button
                keyboard = [
                    [InlineKeyboardButton("🔄 Convert Another File", callback_data='restart')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "Would you like to convert another file?",
                    reply_markup=reply_markup
                )
                
                # Don't return anything here, as we want the separate handler to manage the restart
                return ConversationHandler.END
            else:
                await update.message.reply_text(
                    "❌ Conversion failed. Please try again with a different file."
                )
                cleanup_temp_files([input_path])
                return ConversationHandler.END
                
        except Exception as e:
            logger.error(f"Conversion error: {str(e)}")
            await update.message.reply_text(
                f"❌ Conversion failed: {str(e)}\nPlease try again."
            )
            cleanup_temp_files([input_path])
            return ConversationHandler.END
    
    except Exception as e:
        logger.error(f"File download error: {str(e)}")
        await update.message.reply_text(
            f"❌ Failed to download file: {str(e)}"
        )
        return ConversationHandler.END

# Additional handler for restart callback outside of conversation
async def restart_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle restart callback from outside the conversation."""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    keyboard = [
        [
            InlineKeyboardButton("📷 Image to PDF", callback_data='image_to_pdf'),
            InlineKeyboardButton("📄 Word to PDF", callback_data='word_to_pdf')
        ],
        [
            InlineKeyboardButton("📋 PDF to Word", callback_data='pdf_to_word')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Update the message with the new keyboard
    try:
        await query.edit_message_text(
            f'Hi {user.mention_html()}! 👋\n\n'
            f'I\'m FileConvertBot - your instant file format converter.\n\n'
            f'<b>Choose a conversion type:</b>',
            reply_markup=reply_markup
        )
    except Exception as e:
        # If editing fails, send a new message
        await query.message.reply_text(
            f'Hi {user.mention_html()}! 👋\n\n'
            f'I\'m FileConvertBot - your instant file format converter.\n\n'
            f'<b>Choose a conversion type:</b>',
            reply_markup=reply_markup
        )


def main() -> None:
    """Run the bot."""
    # Create the Application and pass it your bot's token
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set.")
        return
    
    application = Application.builder().token(TOKEN).build()

    # Create conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            START: [
                CallbackQueryHandler(handle_conversion_selection)
            ],
            WAITING_FILE: [MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file_upload)],
        },
        fallbacks=[CommandHandler('start', start)],
        conversation_timeout=300,  # 5 minutes timeout
    )

    application.add_handler(conv_handler)
    # Add the restart handler separately so it works even outside the conversation
    application.add_handler(CallbackQueryHandler(restart_callback_handler, pattern='^restart$'))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()