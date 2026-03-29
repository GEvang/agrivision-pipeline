from agrivision.app.commands.cleanup import cleanup_outputs

if __name__ == '__main__':
    removed = cleanup_outputs()
    print({'removed': removed})
