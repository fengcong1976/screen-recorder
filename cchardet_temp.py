# 临时替代模块，用于cchardet的缺失
def detect(data):
    """模拟cchardet.detect函数"""
    # 默认返回utf-8编码
    return {'encoding': 'utf-8', 'confidence': 0.9}