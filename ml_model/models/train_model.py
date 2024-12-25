from logs.logger import setup_logging
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GridSearchCV
import joblib
import numpy as np
from tqdm import tqdm

logger = setup_logging()

def train_model(X_train, y_train, param_grid=None, cv=3, save_path="best_model.pkl"):
    """
    Train the feedback gain optimization model.

    Parameters:
    - X_train: Training feature data, Pandas DataFrame or Numpy array.
    - y_train: Training target data, Pandas Series or Numpy array.
    - param_grid: dict, hyperparameter grid for grid search (default: None).
    - cv: int, number of cross-validation folds (default: 3).
    - save_path: str, path to save the best trained model (default: "best_model.pkl").

    Returns:
    - best_model: The best estimator from grid search.
    """
    logger.info("Starting model training...")

    # Validate training data
    if np.isnan(X_train.values).any() or np.isinf(X_train.values).any():
        logger.error("X_train contains NaN or Infinity values!")
        raise ValueError("X_train contains NaN or Infinity values!")
    if np.isnan(y_train.values).any() or np.isinf(y_train.values).any():
        logger.error("y_train contains NaN or Infinity values!")
        raise ValueError("y_train contains NaN or Infinity values!")

    logger.info("Training data validation passed.")

    # Default parameter grid
    if param_grid is None:
        param_grid = {
            "n_estimators": [50, 100, 200],
            "max_depth": [5, 10, 20],
            "min_samples_split": [2, 5, 10],
        }

    logger.info(f"Training data size: {len(X_train)} samples")
    logger.info(f"Parameter grid: {param_grid}")

    # Initialize Random Forest Regressor
    model = RandomForestRegressor(random_state=42)

    # Perform Grid Search
    grid_search = GridSearchCV(
        model,
        param_grid,
        cv=cv,
        scoring="neg_mean_squared_error",
        verbose=1,
        error_score="raise"
    )
    try:
        grid_search.fit(X_train, y_train)
    except Exception as e:
        logger.error(f"Grid search failed: {e}")
        raise

    # Log best parameters and score
    logger.info(f"Best parameters: {grid_search.best_params_}")
    logger.info(f"Best score: {grid_search.best_score_}")
    logger.info("Model training completed.")

    # Save the best model
    try:
        logger.info(f"Saving the best model to {save_path}")
        joblib.dump(grid_search.best_estimator_, save_path)
        logger.info("Model saved successfully.")
    except Exception as e:
        logger.error(f"Failed to save model: {e}")
        raise

    return grid_search.best_estimator_
