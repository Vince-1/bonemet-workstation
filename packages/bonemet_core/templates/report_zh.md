# 全身骨显像报告（科研辅助）

**检查编号**：{{ study_uid }}  
**患者编号**：{{ patient_display_id }}  
**签发时间**：{{ approved_at }}

> **免责声明**：本系统为科研辅助工具，输出结果仅供临床参考，不能替代医师独立判断与正式诊断报告；不作为医疗器械注册产品使用。

---

## 检查结论

{{ summary_line }}

## 检查所见

{{ findings_text }}

## 各区域病灶统计

{% if regions %}
| 骨骼区域 | 病灶数 |
|----------|--------|
{% for r in regions %} | {{ r.name }} | {{ r.count }} |
{% endfor %}

**合计**：{{ total_lesions }} 处
{% else %}
未见明确骨转移灶（或已勾选「本例无骨转移」）。
{% endif %}

## 病灶明细

{% for item in lesions %}
- **{{ item.lesion_id }}**（{{ item.view }}）：{{ item.bone_label }} — 置信度 {{ item.conf }}{% if item.assessment_zh %} — {{ item.assessment_zh }}{% endif %}{% if item.lbr %} (LBR {{ item.lbr }}){% endif %}

{% else %}
- 无记录。
{% endfor %}

---

*本报告由 BoneMet Workstation 辅助生成，须经医师审核后签发。*
