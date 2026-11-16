# 示例门店知识库

本目录只包含通用、脱敏的演示资料，不包含任何真实客户或门店专有信息。

在本地试点前，将本目录复制到 `.env` 配置的 `KNOWLEDGE_DIR`，例如：

```powershell
New-Item -ItemType Directory -Force data\knowledge
Copy-Item .\examples\knowledge\*.md .\data\knowledge
```

正式使用时，请由门店负责人审核并替换其中的规则、话术和养护说明。示例内容不构成医疗建议。
