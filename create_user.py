import argparse
import getpass
import sys
import bcrypt
from database import SessionLocal, engine, Base
from models import UserDB


def create_or_update_user(nome: str, username: str, password: str):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = db.query(UserDB).filter(UserDB.username == username).first()
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

        if user:
            user.nome = nome
            user.senha_hash = hashed_password
            db.commit()
            print(f"✅ Usuário '{username}' atualizado com sucesso!")
        else:
            new_user = UserDB(nome=nome, username=username, senha_hash=hashed_password)
            db.add(new_user)
            db.commit()
            print(f"✅ Usuário '{username}' criado com sucesso!")
    finally:
        db.close()


def list_users():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        users = db.query(UserDB).all()
        if not users:
            print("Nenhum usuário cadastrado.")
            return
        print(f"\n{'ID':<5} {'Username':<20} {'Nome':<25} {'Criado em'}")
        print("-" * 65)
        for u in users:
            criado = u.criado_em.strftime("%Y-%m-%d %H:%M") if u.criado_em else "-"
            print(f"{u.id:<5} {u.username:<20} {u.nome:<25} {criado}")
        print()
    finally:
        db.close()


def delete_user(username: str):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = db.query(UserDB).filter(UserDB.username == username).first()
        if not user:
            print(f"❌ Usuário '{username}' não encontrado.")
            return
        db.delete(user)
        db.commit()
        print(f"✅ Usuário '{username}' removido com sucesso!")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Criar ou gerenciar usuários no Valuation App")
    parser.add_argument("--name", "-n", help="Nome do usuário")
    parser.add_argument("--username", "-u", help="Username para login")
    parser.add_argument("--password", "-p", help="Senha")
    parser.add_argument("--list", "-l", action="store_true", help="Listar todos os usuários cadastrados")
    parser.add_argument("--delete", "-d", help="Remover um usuário pelo username")
    args = parser.parse_args()

    if args.list:
        list_users()
        return

    if args.delete:
        delete_user(args.delete)
        return

    nome = args.name
    username = args.username
    password = args.password

    # Modo interativo se não passar argumentos
    if not username:
        username = input("Username: ").strip()
    if not username:
        print("❌ Username não pode ser vazio.")
        sys.exit(1)

    if not nome:
        nome = input(f"Nome completo [{username}]: ").strip() or username

    if not password:
        password = getpass.getpass("Senha: ")
        confirm = getpass.getpass("Confirme a senha: ")
        if password != confirm:
            print("❌ As senhas não coincidem.")
            sys.exit(1)

    if len(password) < 4:
        print("❌ A senha deve ter pelo menos 4 caracteres.")
        sys.exit(1)

    create_or_update_user(nome=nome, username=username, password=password)


if __name__ == "__main__":
    main()
