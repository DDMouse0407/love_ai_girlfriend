import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import payment_gateway


def test_generate_check_mac_value():
    params = {
        "MerchantID": "2000132",
        "MerchantTradeNo": "ecpay2015",
        "MerchantTradeDate": "2015/05/21 13:25:59",
        "PaymentType": "aio",
        "TotalAmount": "1000",
        "TradeDesc": "test",
        "ItemName": "寵物名牌",
        "ReturnURL": "http://192.168.0.1",
        "ChoosePayment": "Credit",
    }
    expected = "C9DCDD1C7477467E75C87D19ADADF99B"
    assert (
        payment_gateway.generate_check_mac_value(
            params, "5294y06JbISpM5x9", "v77hoKGq4kWxNNIS"
        )
        == expected
    )
