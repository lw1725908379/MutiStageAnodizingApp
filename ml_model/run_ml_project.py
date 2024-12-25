import logging
from logs.logger import setup_logging
from ml_model.datasets.preprocess import preprocess_data
from ml_model.datasets.split_data import split_data
from ml_model.models.train_model import train_model
from ml_model.models.evaluate_model import evaluate_model
from ml_model.utils.visualization import (
    plot_feature_distribution,
    plot_correlation_heatmap,
    plot_feature_target_relationship,
    plot_predictions
)
import os

# Initialize logging
logger = setup_logging()

# Define root path for the project
root_path = os.path.normpath("E:/WORKS/py/projects/MultiStageAnodizingApp/ml_model/")

def main():
    """
       Main pipeline for the ML project.
       """
    logger.info("Starting the ML project pipeline...")

    # Step 1: Load and preprocess data
    try:
        logger.info("Loading and preprocessing data...")
        file_path = os.path.normpath(os.path.join(root_path, "datasets/feedback_data.csv"))
        logger.info(f"Using file path: {file_path}")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Data file not found at: {file_path}")
        features, target = preprocess_data(file_path)
        logger.info("Data preprocessing completed successfully.")
    except Exception as e:
        logger.error(f"Error in preprocessing data: {e}")
        return

    # Step 2: Visualize data
    try:
        logger.info("Visualizing data...")
        visualize_path = os.path.normpath(os.path.join(root_path, "outputs/visualizations"))
        plot_feature_distribution(features, save_path=visualize_path)
        plot_correlation_heatmap(features, save_path=visualize_path)
        plot_feature_target_relationship(features.join(target), target_column=target.name, save_path=visualize_path)
        logger.info("Data visualization completed successfully.")
    except Exception as e:
        logger.error(f"Error in visualizing data: {e}")

    # Step 3: Split data into training and testing sets
    try:
        logger.info("Splitting data into training and testing sets...")
        X_train, X_test, y_train, y_test = split_data(features, target)
        logger.info(f"Data split completed: Training set size={len(X_train)}, Testing set size={len(X_test)}")
    except Exception as e:
        logger.error(f"Error in splitting data: {e}")
        return

    # Step 4: Train model
    try:
        logger.info("Training the model...")
        param_grid = {
            "n_estimators": [50, 100, 200],
            "max_depth": [5, 10, 20],
            "min_samples_split": [2, 5, 10],
        }
        model_save_path = os.path.normpath(os.path.join(root_path, "outputs/best_model.pkl"))
        best_model = train_model(X_train, y_train, param_grid=param_grid, save_path=model_save_path)
        logger.info("Model training completed successfully.")
    except Exception as e:
        logger.error(f"Error in training the model: {e}")
        return

    # Step 5: Evaluate model
    try:
        logger.info("Evaluating the model...")
        metrics = evaluate_model(best_model, X_test, y_test)
        logger.info(f"Model evaluation completed: MSE={metrics['mse']}, R2={metrics['r2']}")
    except Exception as e:
        logger.error(f"Error in evaluating the model: {e}")
        return

    # Step 6: Visualize model performance
    try:
        logger.info("Visualizing model performance...")
        performance_path = os.path.normpath(os.path.join(root_path, "outputs/visualizations"))
        plot_predictions(y_test, best_model.predict(X_test), save_path=performance_path)
        logger.info("Model performance visualization completed successfully.")
    except Exception as e:
        logger.error(f"Error in visualizing model performance: {e}")
        return

    logger.info("ML project pipeline completed successfully.")

if __name__ == "__main__":
    main()
