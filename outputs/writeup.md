# Phân tích kết quả tối ưu chi phí GPU cho NimbusAI

## Kết quả chung

Sau khi chạy toàn bộ năm mission, chi phí baseline của NimbusAI là **27.133 USD/tháng**. Sau tối ưu, con số này còn **14.626 USD/tháng**. Như vậy, tổng số tiền có thể tiết kiệm là **12.507 USD/tháng**, tương đương **46,1%**.

Nếu tính cả chi phí hạ tầng theo lượng token phục vụ trong tháng, chi phí giảm từ **120,063 USD xuống 64,720 USD cho mỗi 1 triệu token**. Riêng phần inference API giảm từ **6,488 USD xuống 1,126 USD/1M-token**, tức giảm 82,6%. Tôi tách hai con số này vì chúng phản ánh hai góc nhìn khác nhau: một bên là toàn bộ hóa đơn GPU, còn một bên chỉ cho biết hiệu quả phục vụ request.

## Khoản tiết kiệm đến từ đâu?

Phần tiết kiệm lớn nhất đến từ việc chọn lại hình thức mua GPU. Khi chuyển các workload phù hợp sang spot hoặc reserved, chi phí giảm khoảng **10.040 USD/tháng**. Đây cũng là việc tôi sẽ ưu tiên làm đầu tiên vì tác động lớn hơn hẳn các nhóm còn lại.

Nhóm tối ưu inference tiết kiệm tổng cộng **1.212 USD/tháng**. Trong đó, cascade — chuyển các request đơn giản sang model nhỏ — đóng góp nhiều nhất với **1.122 USD/tháng**. Cache giúp giảm thêm **36 USD**, còn batch giảm thêm **54 USD**. Các mức tiết kiệm này được tính lần lượt trên cùng một lượng traffic, vì thế không bị cộng trùng.

Hai khoản còn lại là khoảng **655 USD/tháng** từ việc right-size GPU có hiệu suất thấp và **600 USD/tháng** từ việc tắt GPU idle. Tuy số tiền nhỏ hơn purchasing, đây vẫn là những việc nên tự động hóa vì có thể giảm lãng phí đều đặn mỗi tháng.

## Trường hợp GPU-Util cao nhưng hiệu quả thấp

Kết quả M1 phát hiện hai trường hợp đáng chú ý. `gpu-h100-4` có GPU-Util khoảng **98,2%** nhưng MFU chỉ **0,194**. `gpu-a10g-1` cũng có GPU-Util khoảng **96,9%**, trong khi MFU chỉ **0,268**.

Về tác động tài chính, báo cáo ước tính việc right-size hai GPU này có thể giảm khoảng **655 USD/tháng**. Ngoài ra, `gpu-h100-5` có 8 giờ gần như idle; nếu tự động tắt phần tài nguyên bỏ không này thì có thể tránh thêm khoảng **600 USD/tháng**. Hai con số trên là ước tính theo giá on-demand trong catalog, chưa tính chi phí chuyển đổi hoặc ảnh hưởng tới hiệu năng.

Theo tôi, đây là ví dụ rõ nhất cho việc không nên nhìn riêng số GPU-Util trong `nvidia-smi`. Chỉ số này cho biết GPU có hoạt động trong thời điểm lấy mẫu, nhưng không cho biết GPU tạo ra bao nhiêu phép tính hữu ích. GPU vẫn có thể báo rất bận khi đang chờ bộ nhớ, chạy nhiều kernel nhỏ, chờ đồng bộ hoặc chịu overhead khi khởi chạy kernel.

Vì vậy, trước khi đổi loại GPU, cần xem thêm MFU, MBU, throughput và `$/1M-token`. Phần right-size trong bài mới là một ước tính ban đầu. Nếu áp dụng vào production, tôi sẽ benchmark lại để chắc chắn rằng latency và throughput không giảm.

## Phần mở rộng 1: Ngân sách cho Reasoning

Trong 2.400 request của bộ dữ liệu có **201 request reasoning**, tương đương **8,4% traffic**. Nhóm này tốn khoảng **1,40 USD/ngày**, chiếm **16,5% chi phí inference sau tối ưu**. Điểm đáng chú ý hơn là reasoning chiếm tới **94,0% điện năng inference ước tính**: khoảng 29.788 Wh/ngày, trong khi 2.199 request thông thường chỉ dùng khoảng 1.888 Wh/ngày.

Tôi thử giới hạn reasoning ở mức 10% số request. Vì traffic hiện tại mới ở mức 8,4%, không có request nào vượt ngưỡng và khoản tiết kiệm đo được là **0 USD, 0 Wh**. Kết quả bằng 0 không có nghĩa là phần mở rộng không có tác dụng; nó cho thấy hệ thống hiện vẫn nằm trong giới hạn đã đặt ra.

Tôi đề xuất chỉ bật reasoning cho câu hỏi thực sự khó hoặc khi model có độ tin cậy thấp. Hệ thống cũng nên cảnh báo khi tỷ lệ reasoning tiến gần 10%. Hệ số năng lượng 80 lần trong bài là giả định minh họa, nên nếu triển khai thật cần thay bằng số đo điện năng thực tế.

## Phần mở rộng 2: Lập lịch theo lượng carbon

Ở phần này, tôi chọn các job có `interruptible=1` vì chúng có thể chuyển thời gian hoặc khu vực chạy dễ hơn. GPU-hours được tính theo số ngày thực tế của từng job, sau đó điện năng được ước lượng bằng mức TDP trong catalog.

Nếu chạy các job này tại `us-east-1`, tổng phát thải ước tính là **679,8 kgCO2e**. Khi chuyển cùng lượng công việc sang `europe-north1`, vùng sạch nhất trong dữ liệu, phát thải còn **53,7 kgCO2e**. Mức giảm là khoảng **626,1 kgCO2e**, tương đương 92,1%. Chi phí điện ước tính cũng giảm từ **214,68 USD xuống 161,01 USD**.

Tuy nhiên, tôi không cho rằng cứ chọn vùng ít carbon nhất là đủ. `europe-north1` là vùng sạch nhất, còn `us-east-wa` mới có giá điện thấp nhất trong catalog. Ngoài tiền điện và carbon, quyết định cuối cùng còn phụ thuộc vào latency, quy định lưu trữ dữ liệu, phí truyền dữ liệu và khả năng thuê được đúng loại GPU. TDP cũng chỉ là mức ước tính; muốn chính xác hơn cần dùng telemetry `power_w` đo trong suốt thời gian job chạy.

## Đề xuất

Nếu phụ trách FinOps cho NimbusAI, tôi sẽ làm ba việc theo thứ tự sau:

1. Phân loại workload theo duty cycle và khả năng checkpoint, sau đó chuyển workload phù hợp sang spot hoặc reserved. Đây là nhóm có mức tiết kiệm lớn nhất trong kết quả hiện tại.
2. Áp dụng cascade, prompt cache và batch cho inference, nhưng đi kèm theo dõi chất lượng đầu ra và độ trễ.
3. Xây dashboard kết hợp GPU-Util, MFU, MBU, điện năng và chi phí theo team. Chỉ bật chargeback khi tag coverage duy trì ổn định trên 80% và các record thiếu project đã được xử lý.

Các mức giá và carbon trong bài là dữ liệu minh họa cho tháng 6/2026. Trước khi dùng để ra quyết định thực tế, cần cập nhật lại bảng giá, carbon intensity và benchmark của workload.
