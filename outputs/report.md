# Báo cáo tối ưu chi phí GPU — NimbusAI

**Kỳ báo cáo:** monthly  
**Chi phí baseline:** $27,133  
**Chi phí sau tối ưu:** $14,626  
**Projected savings (tiết kiệm dự kiến):** $12,507  (**46%**)
**Unit cost baseline:** $120.063/1M-token  
**Unit cost sau tối ưu:** $64.720/1M-token
**Unit cost riêng inference:** $6.488 → $1.126/1M-token

## Tiết kiệm theo từng đòn bẩy

| Đòn bẩy | Tiết kiệm (USD/tháng) |
|---|---|
| Inference (cascade/cache/batch) | $1,212 |
| Purchasing (spot/reserved) | $10,040 |
| Right-size util-lies | $655 |
| Kill idle GPUs | $600 |

### Chi tiết phần tiết kiệm inference

Ba cách tối ưu được áp dụng lần lượt trên cùng một lượng traffic. Vì vậy, các khoản tiết kiệm dưới đây có thể cộng lại mà không bị tính trùng.

| Đòn bẩy inference | Tiết kiệm (USD/ngày) | Tiết kiệm (USD/tháng) |
|---|---:|---:|
| Cascade | $37.40 | $1,122 |
| Cache | $1.20 | $36 |
| Batch | $1.79 | $54 |

## Điện năng và phát thải

- Điện năng mỗi query: 0.24 Wh
- Phát thải mỗi query: 0.091 gCO2e
- Vùng sạch nhất: europe-north1
- Vùng có giá điện thấp nhất: us-east-wa

## Hai phần mở rộng đã thực hiện

### 1. Ngân sách cho Reasoning

Trong bộ dữ liệu này, reasoning chỉ chiếm **8.4% số request**, nhưng lại chiếm **16.5% chi phí inference sau tối ưu** và **94.0% điện năng ước tính**. Khi thử đặt ngưỡng 10%, có **0 request** vượt ngưỡng; mức tiết kiệm tương ứng là **$0.00/ngày** và **0 Wh/ngày**. Traffic hiện tại vốn đã dưới 10%, nên kết quả bằng 0 là hợp lý. Tôi đề xuất chỉ bật reasoning cho câu hỏi khó hoặc khi model có độ tin cậy thấp, đồng thời cảnh báo sớm khi tỷ lệ này gần 10%.

| Nhóm traffic | Số request | Chi phí sau tối ưu/ngày | Điện năng/ngày |
|---|---:|---:|---:|
| Reasoning | 201 | $1.40 | 29,788 Wh |
| Standard | 2199 | $7.09 | 1,888 Wh |
| After 10% cap | 201 reasoning requests | $8.48 total | 31,675 Wh total |

### 2. Lập lịch theo lượng carbon

Tôi thử chuyển các job có thể gián đoạn từ **us-east-1** sang vùng sạch nhất là **europe-north1**. Lượng phát thải ước tính giảm từ **679.8 xuống 53.7 kgCO2e**, tức giảm **626.1 kgCO2e**. Chi phí điện ước tính cũng giảm từ **$214.68 xuống $161.01**. Phép tính dùng số ngày chạy thật của từng job và TDP trong catalog, nên chỉ nên xem là một ước lượng trần. Khi triển khai thật vẫn phải cân nhắc latency, nơi lưu dữ liệu và phí truyền dữ liệu.

| Job có thể gián đoạn | Điện năng | Carbon trước | Carbon sau | Lượng giảm |
|---|---:|---:|---:|---:|
| job-train-llm | 1,568.0 kWh | 595.8 kg | 47.0 kg | 548.8 kg |
| job-train-embed | 80.0 kWh | 30.4 kg | 2.4 kg | 28.0 kg |
| job-finetune | 25.2 kWh | 9.6 kg | 0.8 kg | 8.8 kg |
| job-dev-sandbox | 52.8 kWh | 20.1 kg | 1.6 kg | 18.5 kg |
| job-batch-eval | 63.0 kWh | 23.9 kg | 1.9 kg | 22.1 kg |

## Nhận xét và thứ tự hành động

1. Ưu tiên lại cách mua GPU bằng spot/reserved vì đây là khoản tiết kiệm lớn nhất.
2. Áp dụng cascade, cache và batch, nhưng vẫn phải theo dõi chất lượng đầu ra và độ trễ.
3. Kiểm tra các GPU có util cao nhưng MFU thấp, sau đó tự động tắt GPU idle trước khi chargeback.

GPU-Util cao chỉ cho biết GPU có hoạt động trong lúc lấy mẫu, chứ chưa nói rằng GPU làm việc hiệu quả. Memory stall, kernel nhỏ, đồng bộ hoặc launch overhead vẫn có thể làm GPU trông rất bận trong khi FLOPs hữu ích thấp. Vì vậy cần đọc GPU-Util cùng với MFU, MBU và chi phí trên mỗi triệu token.

_Các con số dùng snapshot tháng 6/2026; cần cập nhật lại trước khi áp dụng thực tế._