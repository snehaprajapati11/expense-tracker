import streamlit as st
import pandas as pd
import sqlite3
import bcrypt
import plotly.express as px
from datetime import datetime
import io
import os
import uuid
import csv
from pathlib import Path

# Page configuration
st.set_page_config(
    page_title="Expense Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .admin-badge {
        background-color: #FF4B4B;
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 0.5rem;
        font-size: 0.8rem;
        font-weight: bold;
    }
    .user-badge {
        background-color: #0068C9;
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 0.5rem;
        font-size: 0.8rem;
        font-weight: bold;
    }
    .stMetric {
        background-color: #f0f2f6;
        border-radius: 0.5rem;
        padding: 1rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# Database initialization
def get_db_path():
    """Get the database path - works locally and on Streamlit Cloud"""
    if os.path.exists('/mount/data'):
        # Streamlit Cloud persistent storage
        Path('/mount/data').mkdir(exist_ok=True)
        return '/mount/data/expense_tracker.db'
    else:
        # Local development
        return 'expense_tracker.db'

def init_db():
    """Initialize the database with required tables"""
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    
    # Create users table if not exists
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        is_admin INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # Create budget table if not exists
    c.execute('''
    CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # Create categories table if not exists
    c.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        type TEXT,
        is_default INTEGER DEFAULT 0
    )
    ''')
    
    # Insert default admin if not exists
    c.execute("SELECT id FROM users WHERE username = 'admin'")
    if not c.fetchone():
        hashed_password = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        c.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)", ('admin', hashed_password))
    
    # Insert default categories if not exists
    c.execute("SELECT id FROM categories LIMIT 1")
    if not c.fetchone():
        default_categories = [
            ('Food', 'expense', 1),
            ('Transportation', 'expense', 1),
            ('Housing', 'expense', 1),
            ('Utilities', 'expense', 1),
            ('Entertainment', 'expense', 1),
            ('Healthcare', 'expense', 1),
            ('Shopping', 'expense', 1),
            ('Other', 'expense', 1),
            ('Salary', 'income', 1),
            ('Bonus', 'income', 1),
            ('Gift', 'income', 1),
            ('Investment', 'income', 1),
            ('Other', 'income', 1)
        ]
        c.executemany("INSERT INTO categories (name, type, is_default) VALUES (?, ?, ?)", default_categories)
    
    conn.commit()
    conn.close()

# Authentication functions
def hash_password(password):
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password, hashed):
    """Verify a password against a hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def register_user(username, password, is_admin=0):
    """Register a new user"""
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    
    # Check if username already exists
    c.execute("SELECT id FROM users WHERE username = ?", (username,))
    if c.fetchone():
        conn.close()
        return False, "Username already exists!"
    
    # Hash the password and insert the new user
    hashed_password = hash_password(password)
    c.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)", 
             (username, hashed_password, is_admin))
    
    user_id = c.lastrowid
    conn.commit()
    conn.close()
    return True, user_id

def login_user(username, password):
    """Login a user"""
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    
    # Fetch user data
    c.execute("SELECT id, password_hash, is_admin FROM users WHERE username = ?", (username,))
    user_data = c.fetchone()
    conn.close()
    
    if not user_data:
        return False, "Username not found!"
    
    user_id, stored_hash, is_admin = user_data
    
    if verify_password(password, stored_hash):
        return True, user_id, is_admin
    else:
        return False, "Incorrect password!", None

def is_user_admin(user_id):
    """Check if a user is an admin"""
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    
    c.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    
    if result:
        return bool(result[0])
    return False

# Data handling functions
def add_transaction(user_id, transaction_type, amount, category, date, note):
    """Add a new transaction to the database"""
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    
    c.execute("""
    INSERT INTO transactions (user_id, type, amount, category, date, note)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, transaction_type, amount, category, date, note))
    
    conn.commit()
    conn.close()
    return True

def get_transactions(user_id, start_date=None, end_date=None, all_users=False):
    """Get transactions with optional filtering"""
    conn = sqlite3.connect(get_db_path())
    
    if all_users:
        query = """
        SELECT t.id, t.user_id, u.username, t.type, t.amount, t.category, t.date, t.note 
        FROM transactions t JOIN users u ON t.user_id = u.id
        """
        params = []
    else:
        query = """
        SELECT id, user_id, type, amount, category, date, note 
        FROM transactions 
        WHERE user_id = ?
        """
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
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    
    # Check if budget already exists
    c.execute("SELECT id FROM budgets WHERE user_id = ?", (user_id,))
    if c.fetchone():
        c.execute("UPDATE budgets SET amount = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?", 
                 (amount, user_id))
    else:
        c.execute("INSERT INTO budgets (user_id, amount) VALUES (?, ?)", (user_id, amount))
    
    conn.commit()
    conn.close()
    return True

def get_budget(user_id):
    """Get a user's monthly budget"""
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    
    c.execute("SELECT amount FROM budgets WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    
    if result:
        return result[0]
    return None

def delete_transaction(transaction_id):
    """Delete a transaction"""
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    
    c.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
    
    conn.commit()
    conn.close()
    return True

def get_all_users():
    """Get all users (for admin panel)"""
    conn = sqlite3.connect(get_db_path())
    query = """
    SELECT u.id, u.username, u.is_admin, u.created_at,
           COUNT(t.id) as transaction_count,
           COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as total_expenses,
           COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) as total_income,
           COALESCE(b.amount, 0) as budget
    FROM users u
    LEFT JOIN transactions t ON u.id = t.user_id
    LEFT JOIN budgets b ON u.id = b.user_id
    GROUP BY u.id
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    return df

def delete_user(user_id):
    """Delete a user and all associated data"""
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    
    # Delete user's transactions
    c.execute("DELETE FROM transactions WHERE user_id = ?", (user_id,))
    
    # Delete user's budget
    c.execute("DELETE FROM budgets WHERE user_id = ?", (user_id,))
    
    # Delete the user
    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    
    conn.commit()
    conn.close()
    return True

def toggle_admin_status(user_id, is_admin):
    """Toggle admin status for a user"""
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    
    c.execute("UPDATE users SET is_admin = ? WHERE id = ?", (1 if is_admin else 0, user_id))
    
    conn.commit()
    conn.close()
    return True

def get_categories(transaction_type=None):
    """Get all categories or categories of a specific type"""
    conn = sqlite3.connect(get_db_path())
    
    if transaction_type:
        query = "SELECT id, name FROM categories WHERE type = ? ORDER BY name"
        df = pd.read_sql_query(query, conn, params=[transaction_type])
    else:
        query = "SELECT id, name, type FROM categories ORDER BY type, name"
        df = pd.read_sql_query(query, conn)
    
    conn.close()
    return df

def add_category(name, category_type):
    """Add a new category"""
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    
    # Check if category already exists
    c.execute("SELECT id FROM categories WHERE name = ? AND type = ?", (name, category_type))
    if c.fetchone():
        conn.close()
        return False, "Category already exists!"
    
    c.execute("INSERT INTO categories (name, type) VALUES (?, ?)", (name, category_type))
    
    conn.commit()
    conn.close()
    return True, "Category added successfully!"

def delete_category(category_id):
    """Delete a category if it's not a default one"""
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    
    # Check if it's a default category
    c.execute("SELECT is_default FROM categories WHERE id = ?", (category_id,))
    result = c.fetchone()
    
    if result and result[0] == 1:
        conn.close()
        return False, "Cannot delete default categories!"
    
    c.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    
    conn.commit()
    conn.close()
    return True, "Category deleted successfully!"

def backup_database():
    """Create backup of database tables in CSV format"""
    tables = ['users', 'transactions', 'budgets', 'categories']
    backup_files = {}
    
    conn = sqlite3.connect(get_db_path())
    
    for table in tables:
        # Create a StringIO object to store CSV data
        csv_data = io.StringIO()
        
        # Query the table
        df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
        
        # Convert to CSV
        df.to_csv(csv_data, index=False)
        
        # Add to backup files
        backup_files[f"{table}.csv"] = csv_data.getvalue()
    
    conn.close()
    
    return backup_files

def import_data_from_csv(file, table):
    """Import data from CSV into specified table"""
    try:
        # Read CSV
        df = pd.read_csv(file)
        
        # Connect to database
        conn = sqlite3.connect(get_db_path())
        
        # Get existing table structure
        existing_cols = pd.read_sql_query(f"PRAGMA table_info({table})", conn)['name'].tolist()
        
        # Filter the dataframe to only include columns in the table
        df = df[[col for col in df.columns if col in existing_cols]]
        
        # Insert data into table
        df.to_sql(table, conn, if_exists='append', index=False)
        
        conn.close()
        return True, f"Successfully imported data into {table}"
    except Exception as e:
        return False, f"Error importing data: {str(e)}"

# UI Components
def show_login_page():
    """Show the landing page with login and signup options"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<h1 style='text-align: center;'>💰 Expense Tracker</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Track your expenses, set budgets, and gain financial insights</p>", unsafe_allow_html=True)
        
        option = st.radio("", ["Login", "Sign Up"], horizontal=True, label_visibility="collapsed")
        
        if option == "Login":
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Login")
                
                if submit:
                    if username and password:
                        success, result, is_admin = login_user(username, password)
                        if success:
                            st.session_state['logged_in'] = True
                            st.session_state['user_id'] = result
                            st.session_state['username'] = username
                            st.session_state['is_admin'] = is_admin
                            st.rerun()
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
                                st.success("Registration successful!")
                                st.info("Please login with your new credentials.")
                            else:
                                st.error(message)
                    else:
                        st.error("Please fill in all fields!")

def show_dashboard(user_id, username, is_admin):
    """Show the main dashboard after login"""
    # Sidebar for navigation
    st.sidebar.title(f"Welcome, {username}!")
    
    if is_admin:
        st.sidebar.markdown("<span class='admin-badge'>Admin</span>", unsafe_allow_html=True)
    else:
        st.sidebar.markdown("<span class='user-badge'>User</span>", unsafe_allow_html=True)
    
    # Create navigation
    if is_admin:
        page = st.sidebar.radio("Navigation", ["Dashboard", "Transactions", "Reports", "Admin Panel", "Settings"])
    else:
        page = st.sidebar.radio("Navigation", ["Dashboard", "Transactions", "Reports", "Settings"])
    
    # Logout button
    if st.sidebar.button("Logout"):
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()
    
    # Display selected page
    if page == "Dashboard":
        show_dashboard_page(user_id)
    elif page == "Transactions":
        show_transactions_page(user_id)
    elif page == "Reports":
        show_reports_page(user_id)
    elif page == "Admin Panel" and is_admin:
        show_admin_panel()
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
            # Get categories from database
            categories_df = get_categories(transaction_type)
            category_list = categories_df['name'].tolist() if not categories_df.empty else []
            
            category = st.selectbox("Category", category_list)
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
                    st.rerun()
    
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
        
        # Color-code transaction types
        def highlight_rows(row):
            if row['type'] == 'income':
                return ['background-color: rgba(46, 204, 113, 0.2)']*len(row)
            else:
                return ['background-color: rgba(231, 76, 60, 0.2)']*len(row)
        
        styled_df = recent_df[['date', 'type', 'amount', 'category', 'note']].style.apply(highlight_rows, axis=1)
        st.dataframe(styled_df, use_container_width=True)
# Corrected get_user_transactions function to align with the database schema
def get_user_transactions(user_id):
    """
    Retrieve all transactions for a specific user from the database.
    
    Parameters:
    user_id (int): The ID of the user whose transactions to retrieve
    
    Returns:
    pandas.DataFrame: DataFrame containing the user's transactions
    """
    conn = sqlite3.connect(get_db_path())
    
    # Query to get all transactions for the specified user
    query = """
    SELECT 
        id, 
        user_id,
        type,
        amount, 
        category,
        date,
        note
    FROM 
        transactions 
    WHERE 
        user_id = ?
    ORDER BY 
        date DESC
    """
    
    # Execute query and load results into a DataFrame
    transactions_df = pd.read_sql(query, conn, params=(user_id,))
    
    conn.close()
    
    if not transactions_df.empty:
        transactions_df['date'] = pd.to_datetime(transactions_df['date'])
    
    return transactions_df

# Corrected show_transactions_page function
def show_transactions_page(user_id):
    """Show the transactions page with list of transactions and add/delete options"""
    st.header("Transactions")
    
    # Retrieve all transactions for the user
    transactions_df = get_user_transactions(user_id)
    
    # Add a new transaction form
    with st.expander("Add New Transaction"):
        with st.form("new_transaction_form"):
            transaction_type = st.selectbox("Transaction Type", ["expense", "income"])
            
            # Get categories for the selected transaction type
            categories_df = get_categories(transaction_type)
            category_list = categories_df['name'].tolist() if not categories_df.empty else []
            
            date = st.date_input("Date", datetime.now())
            amount = st.number_input("Amount", min_value=0.01, step=0.01)
            category = st.selectbox("Category", category_list)
            note = st.text_area("Note (Optional)")
            
            submitted = st.form_submit_button("Add Transaction")
            if submitted:
                if add_transaction(
                    user_id, 
                    transaction_type, 
                    amount, 
                    category, 
                    date.strftime('%Y-%m-%d'), 
                    note
                ):
                    st.success("Transaction added successfully!")
                    st.rerun()
    
    # Display all transactions in a table
    if not transactions_df.empty:
        st.subheader("Your Transactions")
        
        # Format the display dataframe
        display_df = transactions_df.copy()
        display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
        display_df['formatted_amount'] = display_df.apply(
            lambda x: f"${x['amount']:.2f}" if x['type'] == 'income' else f"-${x['amount']:.2f}", 
            axis=1
        )
        
        # Color-code transaction types
        def highlight_rows(row):
            if row['type'] == 'income':
                return ['background-color: rgba(46, 204, 113, 0.2)']*len(row)
            else:
                return ['background-color: rgba(231, 76, 60, 0.2)']*len(row)
        
        styled_df = display_df[['date', 'type', 'formatted_amount', 'category', 'note']].style.apply(highlight_rows, axis=1)
        st.dataframe(styled_df, use_container_width=True)
        
        # Delete transaction option
        with st.expander("Delete a Transaction"):
            # Define a formatter function for transaction display
            def format_transaction(transaction_id):
                # Get the row that matches this transaction ID
                row = transactions_df[transactions_df['id'] == transaction_id].iloc[0]
                
                # Format the entire string with date, category and amount
                date_str = row['date'].strftime('%Y-%m-%d')
                amount_str = f"${float(row['amount']):.2f}"
                return f"{date_str} - {row['category']} ({amount_str})"
            
            transaction_to_delete = st.selectbox(
                "Select transaction to delete",
                transactions_df['id'].tolist(),
                format_func=format_transaction
            )
            
            if st.button("Delete Transaction"):
                delete_transaction(transaction_to_delete)
                st.success("Transaction deleted successfully!")
                st.rerun()
    else:
        st.info("No transactions found. Add your first transaction above.")
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

def show_admin_panel():
    """Show admin panel for user management and system settings"""
    st.title("Admin Panel")
    
    # Create tabs for different admin functions
    tab1, tab2, tab3, tab4 = st.tabs(["User Management", "Category Management", "Data Backup", "System Stats"])
    
    # Tab 1: User Management
    with tab1:
        st.subheader("User Management")
        
        # Get all users
        users_df = get_all_users()
        
        if not users_df.empty:
            # Display user stats with badges for admin
            for _, row in users_df.iterrows():
                with st.container():
                    col1, col2, col3 = st.columns([3, 2, 1])
                    
                    with col1:
                        if row['is_admin']:
                            st.markdown(f"### {row['username']} <span class='admin-badge'>Admin</span>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"### {row['username']} <span class='user-badge'>User</span>", unsafe_allow_html=True)
                        st.text(f"Joined: {row['created_at']}")
                    
                    with col2:
                        st.markdown(f"**Transactions:** {row['transaction_count']}")
                        st.markdown(f"**Total Expenses:** ${row['total_expenses']:.2f}")
                        st.markdown(f"**Total Income:** ${row['total_income']:.2f}")
                        st.markdown(f"**Budget:** ${row['budget']:.2f}")
                    
                    with col3:
                        if row['username'] != 'admin':  # Prevent modifying the default admin
                            # Toggle admin status
                            admin_status = st.checkbox("Admin", value=bool(row['is_admin']), key=f"admin_{row['id']}")
                            
                            if admin_status != bool(row['is_admin']):
                                if toggle_admin_status(row['id'], admin_status):
                                    st.success(f"Updated admin status for {row['username']}")
                                    st.rerun()
                            
                            # Delete user button
                            if st.button("Delete", key=f"delete_{row['id']}"):
                                if st.session_state.get('delete_confirmation') == row['id']:
                                    # Confirmed, delete the user
                                    if delete_user(row['id']):
                                        st.success(f"User {row['username']} deleted successfully!")
                                        st.rerun()
                                    else:
                                        st.error("Failed to delete user!")
                                else:
                                    # Ask for confirmation
                                    st.session_state['delete_confirmation'] = row['id']
                                    st.warning(f"Click again to confirm deletion of {row['username']} and all their data.")
                    
                    st.divider()
        else:
            st.info("No users found.")
        
        # Add new user form
        with st.expander("Add New User"):
            with st.form("add_user_form"):
                new_username = st.text_input("Username")
                new_password = st.text_input("Password", type="password")
                is_admin = st.checkbox("Admin Privileges")
                
                submit = st.form_submit_button("Add User")
                
                if submit:
                    if new_username and new_password:
                        success, message = register_user(new_username, new_password, 1 if is_admin else 0)
                        if success:
                            st.success(f"User {new_username} added successfully!")
                            st.rerun()
                        else:
                            st.error(message)
                    else:
                        st.error("Please enter both username and password!")
    
    # Tab 2: Category Management
    with tab2:
        st.subheader("Category Management")
        
        # Get all categories
        categories_df = get_categories()
        
        if not categories_df.empty:
            # Display categories grouped by type
            expense_categories = categories_df[categories_df['type'] == 'expense']
            income_categories = categories_df[categories_df['type'] == 'income']
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### Expense Categories")
                for _, row in expense_categories.iterrows():
                    col_name, col_action = st.columns([3, 1])
                    col_name.text(row['name'])
                    if not row.get('is_default', 0):  # Only allow deletion of non-default categories
                        if col_action.button("Delete", key=f"del_exp_{row['id']}"):
                            success, message = delete_category(row['id'])
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
            
            with col2:
                st.markdown("### Income Categories")
                for _, row in income_categories.iterrows():
                    col_name, col_action = st.columns([3, 1])
                    col_name.text(row['name'])
                    if not row.get('is_default', 0):  # Only allow deletion of non-default categories
                        if col_action.button("Delete", key=f"del_inc_{row['id']}"):
                            success, message = delete_category(row['id'])
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
        
        # Add new category form
        with st.expander("Add New Category"):
            with st.form("add_category_form"):
                category_name = st.text_input("Category Name")
                category_type = st.selectbox("Category Type", ["expense", "income"])
                
                submit = st.form_submit_button("Add Category")
                
                if submit:
                    if category_name:
                        success, message = add_category(category_name, category_type)
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                    else:
                        st.error("Please enter a category name!")
    
    # Tab 3: Data Backup
    with tab3:
        st.subheader("Data Backup & Import")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Export Database")
            if st.button("Generate Backup"):
                backup_files = backup_database()
                
                for filename, content in backup_files.items():
                    st.download_button(
                        label=f"Download {filename}",
                        data=content,
                        file_name=filename,
                        mime="text/csv",
                        key=f"download_{filename}"
                    )
        
        with col2:
            st.markdown("### Import Data")
            table_to_import = st.selectbox("Select table to import into", 
                                       ["users", "transactions", "budgets", "categories"])
            uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
            
            if uploaded_file is not None:
                if st.button("Import Data"):
                    success, message = import_data_from_csv(uploaded_file, table_to_import)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
    
    # Tab 4: System Stats
    with tab4:
        st.subheader("System Statistics")
        
        # Connect to the database
        conn = sqlite3.connect(get_db_path())
        c = conn.cursor()
        
        # Get system stats
        c.execute("SELECT COUNT(*) FROM users")
        user_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM transactions")
        transaction_count = c.fetchone()[0]
        
        c.execute("SELECT SUM(amount) FROM transactions WHERE type = 'expense'")
        total_expenses = c.fetchone()[0] or 0
        
        c.execute("SELECT SUM(amount) FROM transactions WHERE type = 'income'")
        total_income = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM categories")
        category_count = c.fetchone()[0]
        
        c.execute("SELECT date FROM transactions ORDER BY date DESC LIMIT 1")
        latest_transaction = c.fetchone()
        latest_transaction_date = latest_transaction[0] if latest_transaction else "No transactions"
        
        conn.close()
        
        # Display stats
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Users", user_count)
            st.metric("Total Transactions", transaction_count)
        
        with col2:
            st.metric("Total System Expenses", f"${total_expenses:.2f}")
            st.metric("Total System Income", f"${total_income:.2f}")
        
        with col3:
            st.metric("Total Categories", category_count)
            st.metric("Latest Transaction", latest_transaction_date)
        
        # System health check
        st.markdown("### System Health")
        db_size = os.path.getsize(get_db_path()) / (1024 * 1024)  # Convert to MB
        
        if db_size < 50:
            st.success(f"Database size: {db_size:.2f} MB - Good condition")
        elif db_size < 100:
            st.warning(f"Database size: {db_size:.2f} MB - Consider optimizing soon")
        else:
            st.error(f"Database size: {db_size:.2f} MB - Database is large, consider archiving old data")

def show_settings_page(user_id):
    """Show settings page for user preferences and account settings"""
    st.title("Settings")
    
    # Create tabs for different settings
    tab1, tab2 = st.tabs(["Account Settings", "Preferences"])
    
    # Tab 1: Account Settings
    with tab1:
        st.subheader("Account Settings")
        
        # Change password
        with st.expander("Change Password"):
            with st.form("change_password_form"):
                current_password = st.text_input("Current Password", type="password")
                new_password = st.text_input("New Password", type="password")
                confirm_password = st.text_input("Confirm New Password", type="password")
                
                submit = st.form_submit_button("Change Password")
                
                if submit:
                    if not (current_password and new_password and confirm_password):
                        st.error("Please fill in all fields!")
                    elif new_password != confirm_password:
                        st.error("New passwords do not match!")
                    else:
                        # Verify current password
                        conn = sqlite3.connect(get_db_path())
                        c = conn.cursor()
                        
                        c.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
                        stored_hash = c.fetchone()[0]
                        
                        if verify_password(current_password, stored_hash):
                            # Update with new password
                            new_hash = hash_password(new_password)
                            c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
                            conn.commit()
                            conn.close()
                            
                            st.success("Password changed successfully!")
                        else:
                            conn.close()
                            st.error("Current password is incorrect!")
        
        # Delete account
        with st.expander("Delete Account"):
            st.warning("⚠️ This action cannot be undone. All your data will be permanently deleted.")
            
            with st.form("delete_account_form"):
                confirm_text = st.text_input("Type 'DELETE' to confirm")
                password = st.text_input("Enter your password", type="password")
                
                submit = st.form_submit_button("Delete My Account")
                
                if submit:
                    if confirm_text != "DELETE":
                        st.error("Please type 'DELETE' to confirm!")
                    elif not password:
                        st.error("Please enter your password!")
                    else:
                        # Verify password
                        conn = sqlite3.connect(get_db_path())
                        c = conn.cursor()
                        
                        c.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
                        stored_hash = c.fetchone()[0]
                        
                        if verify_password(password, stored_hash):
                            # Delete the account
                            conn.close()
                            if delete_user(user_id):
                                # Clear session state and redirect to login
                                for key in st.session_state.keys():
                                    del st.session_state[key]
                                st.success("Your account has been deleted.")
                                st.rerun()
                            else:
                                st.error("Failed to delete account!")
                        else:
                            conn.close()
                            st.error("Incorrect password!")
    
    # Tab 2: Preferences
    with tab2:
        st.subheader("Preferences")
        
        # Set monthly budget
        current_budget = get_budget(user_id)
        
        with st.form("budget_form"):
            budget_amount = st.number_input(
                "Set Monthly Budget", 
                min_value=0.0, 
                value=float(current_budget) if current_budget else 0.0,
                format="%.2f"
            )
            
            submit = st.form_submit_button("Save Budget")
            
            if submit:
                if set_budget(user_id, budget_amount):
                    st.success("Budget updated successfully!")
                else:
                    st.error("Failed to update budget!")

# Main app logic
def main():
    # Initialize the database
    init_db()
    
    # Check if user is logged in
    if not st.session_state.get('logged_in', False):
        show_login_page()
    else:
        # User is logged in, show dashboard
        show_dashboard(
            st.session_state['user_id'],
            st.session_state['username'],
            st.session_state['is_admin']
        )

if __name__ == "__main__":
    main()
