import argparse

from sqlalchemy import select

from interview_copilot.infrastructure.database import SessionFactory, UserRecord


def main() -> None:
    parser = argparse.ArgumentParser(description="管理 InterviewCopilot 管理员角色")
    parser.add_argument("action", choices=["grant", "revoke"])
    parser.add_argument("username")
    args = parser.parse_args()

    username = args.username.strip().lower()
    with SessionFactory() as session:
        user = session.scalar(select(UserRecord).where(UserRecord.username == username))
        if not user:
            parser.error("找不到该账号")
        user.role = "admin" if args.action == "grant" else "user"
        session.commit()
        print(f"{user.username}: {user.role}")


if __name__ == "__main__":
    main()
