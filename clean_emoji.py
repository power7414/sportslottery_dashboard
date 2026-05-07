import glob
import emoji

files = ['app.py'] + glob.glob('pages/*.py')
for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Remove all emojis
    clean_content = emoji.replace_emoji(content, replace='')
    
    with open(f, 'w', encoding='utf-8') as file:
        file.write(clean_content)
        
print("Cleaned emojis from:", files)
