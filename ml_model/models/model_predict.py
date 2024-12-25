def predict_kp(model, features):
    """
    使用训练好的模型预测 \(K_p\)。
    """
    return model.predict(features)
