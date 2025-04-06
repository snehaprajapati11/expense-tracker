import streamlit as st
import pandas as pd
import sqlite3
import bcrypt
import plotly.express as px
from datetime import datetime
import io
import os

# Page configuration
st.set_page_config(
    page_title="Expense Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database initialization
def init_db():
    conn = sqlite3.connect('expense_tracker.db')
    c = conn.cursor()
    
    # Create users table if not exists
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT
    )
    ''')
    
    # Create transactions table if not exists
    c.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        amount REAL,
        category TEXT,
        date TEXT,
        note TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # Create budget table if not exists
    c.execute('''
    CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    conn.commit()
    conn.close()

# Call DB initialization
init_db()

# Authentication functions
def hash_password(password):
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password, hashed):
    """Verify a password against a hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def register_user(username, password):
    """Register a new user"""
    conn = sqlite3.connect('expense_tracker.db')
    c = conn.cursor()
    
    # Check if username already exists
    c.execute("SELECT id FROM users WHERE username = ?", (username,))
    if c.fetchone():
        conn.close()
        return False, "Username already exists!"
    
    # Hash the password and insert the new user
    hashed_password = hash_password(password)
    c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hashed_password))
    conn.commit()
    conn.close()
    return True, "Registration successful!"

def login_user(username, password):
    """Login a user"""
    conn = sqlite3.connect('expense_tracker.db')
    c = conn.cursor()
    
    # Fetch user data
    c.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,))
    user_data = c.fetchone()
    conn.close()
    
    if not user_data:
        return False, "Username not found!"
    
    user_id, stored_hash = user_data
    
    if verify_password(password, stored_hash):
        return True, user_id
    else:
        return False, "Incorrect password!"

# Data handling functions
def add_transaction(user_id, transaction_type, amount, category, date, note):
    """Add a new transaction to the database"""
    conn = sqlite3.connect('expense_tracker.db')
    c = conn.cursor()
    
    c.execute("""
    INSERT INTO transactions (user_id, type, amount, category, date, note)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, transaction_type, amount, category, date, note))
    
    conn.commit()
    conn.close()
    return True

def get_transactions(user_id, start_date=None, end_date=None):
    """Get transactions for a user with optional date filtering"""
    conn = sqlite3.connect('expense_tracker.db')
    
    query = "SELECT id, type, amount, category, date, note FROM transactions WHERE user_id = ?"
    params = [user_id]
    
    if start_date and end_date:
        query += " AND date BETWEEN ? AND ?"
        params.extend([start_date, end_date])
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values(by='date', ascending=False)
    
    return df

def set_budget(user_id, amount):
    """Set or update a user's monthly budget"""
    conn = sqlite3.connect('expense_tracker.db')
    c = conn.cursor()
    
    # Check if budget already exists
    c.execute("SELECT id FROM budgets WHERE user_id = ?", (user_id,))
    if c.fetchone():
        c.execute("UPDATE budgets SET amount = ? WHERE user_id = ?", (amount, user_id))
    else:
        c.execute("INSERT INTO budgets (user_id, amount) VALUES (?, ?)", (user_id, amount))
    
    conn.commit()
    conn.close()
    return True

def get_budget(user_id):
    """Get a user's monthly budget"""
    conn = sqlite3.connect('expense_tracker.db')
    c = conn.cursor()
    
    c.execute("SELECT amount FROM budgets WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    
    if result:
        return result[0]
    return None

def delete_transaction(transaction_id):
    """Delete a transaction"""
    conn = sqlite3.connect('expense_tracker.db')
    c = conn.cursor()
    
    c.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
    
    conn.commit()
    conn.close()
    return True

# UI Components
def show_landing_page():
    """Show the landing page with login and signup options"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<h1 style='text-align: center;'>💰 Expense Tracker</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Track your expenses, set budgets, and gain financial insights</p>", unsafe_allow_html=True)
        
        option = st.radio("", ["Login", "Sign Up"], horizontal=True)
        
        if option == "Login":
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Login")
                
                if submit:
                    if username and password:
                        success, result = login_user(username, password)
                        if success:
                            st.session_state['logged_in'] = True
                            st.session_state['user_id'] = result
                            st.session_state['username'] = username
                            st.experimental_rerun()
                        else:
                            st.error(result)
                    else:
                        st.error("Please enter both username and password!")
        
        else:  # Sign Up
            with st.form("signup_form"):
                new_username = st.text_input("Choose Username")
                new_password = st.text_input("Choose Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                submit = st.form_submit_button("Sign Up")
                
                if submit:
                    if new_username and new_password and confirm_password:
                        if new_password != confirm_password:
                            st.error("Passwords do not match!")
                        else:
                            success, message = register_user(new_username, new_password)
                            if success:
                                st.success(message)
                                st.info("Please login with your new credentials.")
                            else:
                                st.error(message)
                    else:
                        st.error("Please fill in all fields!")

def show_dashboard(user_id, username):
    """Show the main dashboard after login"""
    # Sidebar for navigation
    st.sidebar.title(f"Welcome, {username}!")
    
    # Create navigation
    page = st.sidebar.radio("Navigation", ["Dashboard", "Transactions", "Reports", "Settings"])
    
    # Logout button
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.session_state['user_id'] = None
        st.session_state['username'] = None
        st.experimental_rerun()
    
    # Display selected page
    if page == "Dashboard":
        show_dashboard_page(user_id)
    elif page == "Transactions":
        show_transactions_page(user_id)
    elif page == "Reports":
        show_reports_page(user_id)
    elif page == "Settings":
        show_settings_page(user_id)

def show_dashboard_page(user_id):
    """Show the dashboard overview page"""
    st.title("Dashboard")
    
    # Get current month's transactions
    today = datetime.now()
    start_of_month = today.replace(day=1).strftime('%Y-%m-%d')
    end_of_month = datetime(today.year, today.month + 1, 1).strftime('%Y-%m-%d') if today.month < 12 else datetime(today.year + 1, 1, 1).strftime('%Y-%m-%d')
    
    transactions_df = get_transactions(user_id, start_of_month, end_of_month)
    
    # Calculate summaries
    if transactions_df.empty:
        total_income = 0
        total_expenses = 0
    else:
        total_income = transactions_df[transactions_df['type'] == 'income']['amount'].sum()
        total_expenses = transactions_df[transactions_df['type'] == 'expense']['amount'].sum()
    
    balance = total_income - total_expenses
    
    # Budget check
    budget = get_budget(user_id)
    
    # Display summary cards
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Income", f"${total_income:.2f}", delta=None)
    with col2:
        st.metric("Total Expenses", f"${total_expenses:.2f}", delta=None)
    with col3:
        st.metric("Balance", f"${balance:.2f}", delta=None)
    
    # Budget warning
    if budget and total_expenses > budget:
        st.warning(f"⚠️ You've exceeded your monthly budget by ${total_expenses - budget:.2f}")
    elif budget:
        st.success(f"You're within your monthly budget. Remaining: ${budget - total_expenses:.2f}")
    
    # Add new transaction form
    st.subheader("Add New Transaction")
    
    with st.form("transaction_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            transaction_type = st.selectbox("Transaction Type", ["expense", "income"])
            amount = st.number_input("Amount", min_value=0.01, format="%.2f")
            
        with col2:
            categories = {
                "expense": ["Food", "Transportation", "Housing", "Utilities", "Entertainment", "Healthcare", "Shopping", "Other"],
                "income": ["Salary", "Bonus", "Gift", "Investment", "Other"]
            }
            
            category = st.selectbox("Category", categories[transaction_type])
            date = st.date_input("Date", datetime.now())
        
        note = st.text_area("Note (Optional)", height=100)
        submit = st.form_submit_button("Add Transaction")
        
        if submit:
            if amount <= 0:
                st.error("Amount must be greater than zero!")
            else:
                success = add_transaction(
                    user_id, 
                    transaction_type, 
                    amount, 
                    category, 
                    date.strftime('%Y-%m-%d'), 
                    note
                )
                if success:
                    st.success("Transaction added successfully!")
                    st.experimental_rerun()
    
    # Recent transactions
    st.subheader("Recent Transactions")
    if transactions_df.empty:
        st.info("No transactions found for this month.")
    else:
        # Show the 5 most recent transactions
        recent_df = transactions_df.head(5).copy()
        recent_df['amount'] = recent_df.apply(
            lambda x: f"${x['amount']:.2f}" if x['type'] == 'income' else f"-${x['amount']:.2f}", 
            axis=1
        )
        recent_df['date'] = recent_df['date'].dt.strftime('%Y-%m-%d')
        st.dataframe(
            recent_df[['date', 'type', 'amount', 'category', 'note']],
            use_container_width=True,
            hide_index=True
        )

def show_transactions_page(user_id):
    """Show all transactions with filtering options"""
    st.title("Transactions")
    
    # Date filters
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", datetime.now().replace(day=1))
    with col2:
        end_date = st.date_input("End Date", datetime.now())
    
    # Convert to string format for SQLite
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    # Get filtered transactions
    transactions_df = get_transactions(user_id, start_date_str, end_date_str)
    
    # Add delete button functionality
    if not transactions_df.empty:
        # Add a column for delete buttons
        transactions_display = transactions_df.copy()
        transactions_display['amount'] = transactions_display.apply(
            lambda x: f"${x['amount']:.2f}" if x['type'] == 'income' else f"-${x['amount']:.2f}", 
            axis=1
        )
        transactions_display['date'] = transactions_display['date'].dt.strftime('%Y-%m-%d')
        
        st.dataframe(
            transactions_display[['date', 'type', 'amount', 'category', 'note']],
            use_container_width=True,
            hide_index=True
        )
        
        # Delete transaction option
        with st.expander("Delete a Transaction"):
            transaction_to_delete = st.selectbox(
                "Select transaction to delete", 
                transactions_df['id'].tolist(),
                format_func=lambda x: f"{transactions_df[transactions_df['id'] == x]['date'].values[0].strftime('%Y-%m-%d')} - {transactions_df[transactions_df['id'] == x]['category'].values[0]} - ${transactions_df[transactions_df['id'] == x]['amount'].values[0]:.2f}"
            )
            
            if st.button("Delete Transaction"):
                if delete_transaction(transaction_to_delete):
                    st.success("Transaction deleted successfully!")
                    st.experimental_rerun()
                else:
                    st.error("Failed to delete transaction!")
        
        # Export to CSV
        if st.button("Export to CSV"):
            csv = io.StringIO()
            export_df = transactions_display[['date', 'type', 'amount', 'category', 'note']]
            export_df.to_csv(csv, index=False)
            
            st.download_button(
                label="Download CSV",
                data=csv.getvalue(),
                file_name=f"transactions_{start_date_str}_to_{end_date_str}.csv",
                mime="text/csv"
            )
    else:
        st.info("No transactions found for the selected date range.")

def show_reports_page(user_id):
    """Show reports and analytics"""
    st.title("Reports & Analytics")
    
    # Date filters
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", datetime.now().replace(day=1))
    with col2:
        end_date = st.date_input("End Date", datetime.now())
    
    # Convert to string format for SQLite
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    # Get filtered transactions
    transactions_df = get_transactions(user_id, start_date_str, end_date_str)
    
    if transactions_df.empty:
        st.info("No transactions found for the selected date range.")
        return
    
    # Calculate summaries
    total_income = transactions_df[transactions_df['type'] == 'income']['amount'].sum()
    total_expenses = transactions_df[transactions_df['type'] == 'expense']['amount'].sum()
    balance = total_income - total_expenses
    
    # Display summary cards
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Income", f"${total_income:.2f}")
    with col2:
        st.metric("Total Expenses", f"${total_expenses:.2f}")
    with col3:
        st.metric("Balance", f"${balance:.2f}")
    
    # Expenses by category
    st.subheader("Expense Distribution by Category")
    
    expenses_df = transactions_df[transactions_df['type'] == 'expense']
    
    if not expenses_df.empty:
        expense_by_category = expenses_df.groupby('category')['amount'].sum().reset_index()
        
        fig = px.pie(
            expense_by_category, 
            values='amount', 
            names='category',
            title='Expense Distribution',
            hole=0.4,
            color_discrete_sequence=px.colors.sequential.Viridis
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No expense data available for the selected period.")
    
    # Income by category
    st.subheader("Income Distribution by Category")
    
    income_df = transactions_df[transactions_df['type'] == 'income']
    
    if not income_df.empty:
        income_by_category = income_df.groupby('category')['amount'].sum().reset_index()
        
        fig = px.pie(
            income_by_category, 
            values='amount', 
            names='category',
            title='Income Distribution',
            hole=0.4,
            color_discrete_sequence=px.colors.sequential.Plasma
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No income data available for the selected period.")
    
    # Monthly trend
    st.subheader("Monthly Trend")
    
    if not transactions_df.empty:
        # Add month column
        transactions_df['month'] = transactions_df['date'].dt.strftime('%Y-%m')
        
        # Group by month and type
        monthly_data = transactions_df.groupby(['month', 'type'])['amount'].sum().reset_index()
        
        # Pivot data for better visualization
        pivot_data = monthly_data.pivot(index='month', columns='type', values='amount').reset_index()
        pivot_data = pivot_data.fillna(0)
        
        # Ensure both columns exist
        if 'expense' not in pivot_data.columns:
            pivot_data['expense'] = 0
        if 'income' not in pivot_data.columns:
            pivot_data['income'] = 0
        
        # Create the bar chart
        fig = px.bar(
            pivot_data,
            x='month',
            y=['income', 'expense'],
            title='Monthly Income vs Expenses',
            barmode='group',
            labels={'value': 'Amount', 'variable': 'Type'},
            color_discrete_map={'income': '#36A2EB', 'expense': '#FF6384'}
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Not enough data for monthly trend visualization.")

def show_settings_page(user_id):
    """Show settings for the user"""
    st.title("Settings")
    
    # Budget settings
    st.subheader("Monthly Budget")
    
    current_budget = get_budget(user_id)
    
    with st.form("budget_form"):
        new_budget = st.number_input(
            "Set Monthly Budget", 
            min_value=0.0, 
            value=float(current_budget) if current_budget else 0.0,
            format="%.2f"
        )
        
        submit = st.form_submit_button("Update Budget")
        
        if submit:
            if set_budget(user_id, new_budget):
                st.success("Budget updated successfully!")
            else:
                st.error("Failed to update budget!")

# Main App Logic
def main():
    # Initialize session state
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['user_id'] = None
        st.session_state['username'] = None
    
    # Display the appropriate page based on login status
    if st.session_state['logged_in']:
        show_dashboard(st.session_state['user_id'], st.session_state['username'])
    else:
        show_landing_page()

if __name__ == "__main__":
    main()
