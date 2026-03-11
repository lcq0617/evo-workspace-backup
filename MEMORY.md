# 核心记忆 (compressed)

- - 曾踩的坑：
- - 初次 init 时误把 token 写入 remote URL（已移除并建议旋转 token）。
- - Windows 下 CRLF 导致回滚后的工作树多出空行（已加入 .gitattributes 与 LF 归一化）。
- - git commit -> 记录 .backups/<commit>.json
- - git reset --hard <commit> && git clean -fd  -> 回滚
- - just backup || git add -A && git commit -m "..." -> 备份优先策略
