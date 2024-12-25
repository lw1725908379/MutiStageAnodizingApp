from sklearn.metrics import mean_squared_error, r2_score

def evaluate_model(model, X_test, y_test):
    """
    Evaluate the performance of a trained model.

    Parameters:
    - model: Trained model to evaluate.
    - X_test: Test feature data, Pandas DataFrame or Numpy array.
    - y_test: True target values for the test set, Pandas Series or Numpy array.

    Returns:
    - metrics: dict, containing mean squared error (mse) and R-squared (r2).
    """
    # Predict using the model
    predictions = model.predict(X_test)

    # Compute performance metrics
    mse = mean_squared_error(y_test, predictions)
    r2 = r2_score(y_test, predictions)

    return {"mse": mse, "r2": r2}
