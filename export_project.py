import fnmatch
import sys
from pathlib import Path


def load_gitignore_patterns(gitignore_path):
    patterns = []
    if not gitignore_path.exists():
        return patterns
    with open(gitignore_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Убираем завершающий слеш для папок (но сохраняем информацию)
            # Для сравнения будем использовать как есть, но при проверке папок
            # будем учитывать
            patterns.append(line)
    return patterns


def is_ignored(path, patterns, root_dir):
    rel_path = path.relative_to(root_dir)
    rel_str = str(rel_path).replace('\\', '/')  # унифицируем разделители

    for pat in patterns:
        # Нормализуем паттерн: убираем ведущий слеш, если есть
        if pat.startswith('/'):
            pat = pat[1:]
        # Если паттерн заканчивается на '/', это значит папка
        if pat.endswith('/'):
            # Проверяем, является ли путь папкой (или содержимым)
            if path.is_dir():
                # Проверяем, что путь совпадает с именем папки или начинается с
                # неё
                if rel_str == pat[:-1] or rel_str.startswith(pat[:-1] + '/'):
                    return True
            else:
                # Для файлов: игнорируем, если путь лежит внутри такой папки
                if rel_str.startswith(pat[:-1] + '/'):
                    return True
        else:
            # Обычный паттерн для файлов или папок без завершающего слеша
            if fnmatch.fnmatch(rel_str, pat):
                return True
            # Если паттерн с '*' в конце, может означать частичное совпадение
            if pat.endswith('*') and rel_str.startswith(pat[:-1]):
                return True
    return False


def print_tree(out, root_dir, patterns, prefix=""):
    items = sorted([p for p in root_dir.iterdir() if not is_ignored(
        p, patterns, root_dir.parent)])
    for i, item in enumerate(items):
        is_last = i == len(items) - 1
        if item.is_dir():
            out.write(f"{prefix}{'└── ' if is_last else '├── '}{item.name}/\n")
            new_prefix = prefix + ('    ' if is_last else '│   ')
            print_tree(out, item, patterns, new_prefix)
        else:
            out.write(f"{prefix}{'└── ' if is_last else '├── '}{item.name}\n")


def print_file_contents(out, root_dir, patterns):
    for path in sorted(root_dir.rglob('*')):
        if path.is_dir() or is_ignored(path, patterns, root_dir):
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            continue
        except Exception as e:
            out.write(f"\n[Ошибка чтения {path}]: {e}\n")
            continue

        rel_path = path.relative_to(root_dir)
        out.write(f"\n{'='*80}\n")
        out.write(f"Файл: {rel_path}\n")
        out.write(f"{'='*80}\n")
        out.write(content)
        out.write("\n")


def main():
    root = Path.cwd()
    gitignore_path = root / '.gitignore'
    patterns = load_gitignore_patterns(gitignore_path)

    # Добавляем стандартные игнорируемые папки (на случай, если их нет в
    # .gitignore)
    default_ignored = [
        'venv/', 'env/', '__pycache__/', '.git/', 'media/', 'staticfiles/',
        'static_root/', '.env', '*.pyc', 'db.sqlite3'
    ]
    patterns.extend(default_ignored)

    output_filename = sys.argv[1] if len(sys.argv) > 1 else 'project_dump.txt'

    with open(output_filename, 'w', encoding='utf-8') as out:
        out.write(f"Структура проекта: {root}\n")
        out.write("=" * 80 + "\n")
        print_tree(out, root, patterns, "")
        out.write("\n\n" + "="*80 + " СОДЕРЖИМОЕ ФАЙЛОВ " + "="*80 + "\n")
        print_file_contents(out, root, patterns)

    print(f"Готово! Результат сохранён в {output_filename}")


if __name__ == "__main__":
    main()
