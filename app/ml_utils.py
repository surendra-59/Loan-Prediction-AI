import pandas as pd


def prepare_user_input(user_data):
    """
    Convert raw user input into model-ready format
    """

    df = pd.DataFrame([user_data])

    model_cols = [
        'Age','Income','LoanAmount','CreditScore','MonthsEmployed','NumCreditLines',
        'InterestRate','LoanTerm','DTIRatio',
        "Education_High School","Education_Master's","Education_PhD",
        "EmploymentType_Part-time","EmploymentType_Self-employed","EmploymentType_Unemployed",
        "MaritalStatus_Married","MaritalStatus_Single",
        "HasMortgage_Yes","HasDependents_Yes","HasCoSigner_Yes"
    ]

    model_input = pd.DataFrame(0, index=[0], columns=model_cols)

    numeric_cols = [
        'Age','Income','LoanAmount','CreditScore','MonthsEmployed',
        'NumCreditLines','InterestRate','LoanTerm','DTIRatio'
    ]

    model_input[numeric_cols] = df[numeric_cols]

    # Education (Bachelor's is base case)
    edu_map = {
        'High School': "Education_High School",
        "Master's": "Education_Master's",
        "PhD": "Education_PhD"
    }

    if user_data['Education'] in edu_map:
        model_input[edu_map[user_data['Education']]] = 1

    # Employment (Full-time base case)
    emp_map = {
        'Part-time': "EmploymentType_Part-time",
        'Self-employed': "EmploymentType_Self-employed",
        'Unemployed': "EmploymentType_Unemployed"
    }

    if user_data['EmploymentType'] in emp_map:
        model_input[emp_map[user_data['EmploymentType']]] = 1

    # Marital (Divorced base case)
    marital_map = {
        'Married': "MaritalStatus_Married",
        'Single': "MaritalStatus_Single"
    }

    if user_data['MaritalStatus'] in marital_map:
        model_input[marital_map[user_data['MaritalStatus']]] = 1

    yes_no_map = {'Yes': 1, 'No': 0}

    model_input['HasMortgage_Yes'] = yes_no_map[user_data['HasMortgage']]
    model_input['HasDependents_Yes'] = yes_no_map[user_data['HasDependents']]
    model_input['HasCoSigner_Yes'] = yes_no_map[user_data['HasCoSigner']]

    return model_input